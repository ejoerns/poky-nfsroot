import os
import logging
import subprocess
import datetime

import oe.path
from oe.rootfs import generate_index_files
from oe.package_manager.ipk import OpkgPM
from oe.package_manager.rpm import RpmPM
from oe.package_manager.deb import DpkgPM

log = logging.getLogger('nfs-export-updater')

# implement missing 'upgrade' method
def upgrade(pkgmgr):
    pkgmgr.deploy_dir_lock()

    cmd = "%s %s upgrade" % (pkgmgr.opkg_cmd, pkgmgr.opkg_args)

    os.environ['D'] = pkgmgr.target_rootfs
    os.environ['OFFLINE_ROOT'] = pkgmgr.target_rootfs
    os.environ['IPKG_OFFLINE_ROOT'] = pkgmgr.target_rootfs
    os.environ['OPKG_OFFLINE_ROOT'] = pkgmgr.target_rootfs
    os.environ['INTERCEPT_DIR'] = pkgmgr.intercepts_dir
    os.environ['NATIVE_ROOT'] = pkgmgr.d.getVar('STAGING_DIR_NATIVE')

    try:
        output = subprocess.check_output(cmd.split(), stderr=subprocess.STDOUT).decode('utf-8')
        log.debug("Upgrade output:")
        log.debug(output)
        for line in output.split('\n'):
            if line.startswith("Installing"):
                log.info("Installing: %s" % line.split(" ")[1])
            if line.startswith("Upgrading"):
                log.info("Upgrading: %s" % line.split(" ")[1])
    except subprocess.CalledProcessError as e:
        pkgmgr.deploy_dir_unlock()
        print("Unable to update the package index files. Command '%s' "
                 "returned %d:\n%s" % (cmd, e.returncode, e.output.decode("utf-8")))

    pkgmgr.deploy_dir_unlock()


def list_pkgs(pkgmgr):
    cmd = "%s %s list" % (pkgmgr.opkg_cmd, pkgmgr.opkg_args)

    try:
        output = subprocess.check_output(cmd.split(), stderr=subprocess.STDOUT)
        print("Available Packages:")
        print(output.decode('utf-8'))
    except subprocess.CalledProcessError as e:
        pkgmgr.deploy_dir_unlock()
        print("Unable to update the package index files. Command '%s' "
                 "returned %d:\n%s" % (cmd, e.returncode, e.output.decode("utf-8")))


def add_tool_to_path(tinfoil, native_recipe, toolname, bindir="/usr/bin", pseudo_wrapper=False):
    # add opkg to PATH
    rd = tinfoil.parse_recipe(native_recipe)
    staging_bindir_native = '%s%s' % (rd.getVar("STAGING_DIR_NATIVE"), bindir)

    log.debug("Testing native tool: %s" % os.path.join(staging_bindir_native, toolname))
    if not os.path.exists(os.path.join(staging_bindir_native, toolname)):
        log.info(f"Adding '{toolname}' to '{native_recipe}' recipe sysroot")
        tinfoil.build_targets(native_recipe, task="addto_recipe_sysroot")
        if not os.path.exists(os.path.join(staging_bindir_native, toolname)):
            raise Exception(f"Failed adding '{toolname}' to '{native_recipe}' recipe sysroot")
    else:
        log.info(f"'{toolname}' already existing in '{native_recipe}' recipe sysroot")

    if pseudo_wrapper:
        # Create pseudo wrapper for tools
        rd = tinfoil.parse_recipe("pseudo-native")
        pseudo_native_prefix = '%s/usr' % rd.getVar("STAGING_DIR_NATIVE")
        pseudo_native_bin = '%s/bin/pseudo' % pseudo_native_prefix
        wrapper_path = os.path.join(rd.getVar("TMPDIR"), "pseudo-wrapper/bin")
        os.makedirs(wrapper_path, exist_ok=True)
        tool_path = os.path.join(wrapper_path, toolname)
        with open(tool_path, "w") as f:
            f.write(f"#!/bin/sh\n{pseudo_native_bin} -P {pseudo_native_prefix} {staging_bindir_native}/{toolname} \"$@\"\n")
        os.chmod(tool_path, 0o755)
        os.environ['PATH'] = wrapper_path + ":" + os.environ['PATH']
    else:
        os.environ["PATH"] = staging_bindir_native + ":" + os.environ["PATH"]

def add_crosstool_to_path(tinfoil, cross_recipe, toolname, bindir="/usr/bin/crossscripts"):
    # add opkg to PATH
    rd = tinfoil.parse_recipe(cross_recipe)
    staging_bindir_cross = '%s/%s/%s%s' % (rd.getVar("COMPONENTS_DIR"), rd.getVar("MACHINE_ARCH"), cross_recipe, bindir)

    log.debug("Testing cross tool: %s" % os.path.join(staging_bindir_cross, toolname))
    if not os.path.exists(os.path.join(staging_bindir_cross, toolname)):
        log.info(f"Adding '{toolname}' to '{cross_recipe}' recipe sysroot")
        tinfoil.build_targets(cross_recipe)
        if not os.path.exists(os.path.join(staging_bindir_cross, toolname)):
            raise Exception(f"Failed adding '{toolname}' to '{cross_recipe}' recipe sysroot")
    else:
        log.info(f"'{toolname}' already existing in '{cross_recipe}' recipe sysroot")

    os.environ["PATH"] = staging_bindir_cross + ":" + os.environ["PATH"]

def prepare_native_tools():
    import bb.tinfoil

    with bb.tinfoil.Tinfoil() as tinfoil:
        tinfoil.prepare(quiet=1)

        # set to prevent recursive server calls
        tinfoil.config_data.setVar("NFS_UPDATER_INTERNAL", "1")

        pkg_type = tinfoil.config_data.getVar("PACKAGE_CLASSES").split()[0].replace("package_", "")
        log.info(f"Creating Carabiner for {pkg_type}")

        # add common tools
        log.info("Adding required tools to their recipe sysroot...")
        add_tool_to_path(tinfoil, "virtual/update-alternatives-native", "update-alternatives")
        add_tool_to_path(tinfoil, "shadow-native", "pwconv", bindir="/usr/sbin")
        add_tool_to_path(tinfoil, "pseudo-native", "pseudo")
        add_tool_to_path(tinfoil, "kmod-native", "depmod", bindir="/sbin")
        add_crosstool_to_path(tinfoil, "depmodwrapper-cross", "depmodwrapper")

        # add package manager-specific tools
        if pkg_type == 'ipk':
            add_tool_to_path(tinfoil, "opkg-native", "opkg", pseudo_wrapper=True)
            # opkg-utils native for opkg-make-index
            add_tool_to_path(tinfoil, "opkg-utils-native", "opkg-make-index")
        elif pkg_type == 'rpm':
            add_tool_to_path(tinfoil, "dnf-native", "dnf")
            add_tool_to_path(tinfoil, "createrepo-c-native", "createrepo_c")
        elif pkg_type == 'deb':
            log.warn("Package type 'deb' is not supported, yet")

        log.debug("Full PATH is now: " + os.environ["PATH"])


def write_stamp_file(nfsroot):
    datetime_now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    stamppath = "/etc/nfs-export-updated"
    log.info(f"Writing update timestamp {datetime_now} to stamp file {stamppath} ...")
    with open(oe.path.join(nfsroot, stamppath), "w") as f:
        f.write(f"{datetime_now}\n")


def get_package_manager(d, nfsroot):
    pkg_type = d.getVar("PACKAGE_CLASSES").split()[0].replace("package_", "")

    if pkg_type == "ipk":
        # Set up ipkg package feed
        ipkgconf = d.getVar("IPKGCONF_TARGET")
        archs = d.getVar("ALL_MULTILIB_PACKAGE_ARCHS")
        ipk_dir = d.getVar('DEPLOY_DIR_IPK')
        feed_uris = ""
        # Create feed uri entries as expected by IPK_FEED_URIS:
        # Space-seperated list of '<arch>##<uri>' entries
        for arch in archs.split():
            # need to filter out non-exisiting dirs to prevent package update
            # failures
            if os.path.isdir(os.path.join(ipk_dir, arch)):
                feed_uris += "%s##file://%s/%s " % (arch, ipk_dir, arch)
        d.setVar("BUILD_IMAGES_FROM_FEEDS", "1")
        d.setVar("IPK_FEED_URIS", feed_uris)

        return OpkgPM(d, nfsroot, ipkgconf, archs, prepare_index=False)
    elif pkg_type == "rpm":
        log.warning(f"Package type {pkg_type} not supported")
        target_vendor = d.getVar('TARGET_VENDOR')
        return RpmPM(d, nfsroot, target_vendor)
    elif pkg_type == "deb":
        log.warning(f"Package type {pkg_type} not supported")
        package_archs = d.getVar('PACKAGE_ARCHS'),
        dpkg_arch = d.getVar('DPKG_ARCH'),
        return DpkgPM(d, nfsroot, package_archs, dpkg_arch)
    else:
        raise Exception(f"Invalid package type {pkg_type}")


def update_packages(rootfs_recipe, nfsroot):
    import bb.tinfoil

    with bb.tinfoil.Tinfoil() as tinfoil:
        tinfoil.prepare(quiet=1)

        # set to prevent recursive server calls
        tinfoil.config_data.setVar("NFS_UPDATER_INTERNAL", "1")

        log.debug(f"Updating nfsroot: {nfsroot}")

        # get packages to install
        rd = tinfoil.parse_recipe(rootfs_recipe)
        pkgs = rd.getVar("IMAGE_INSTALL").split()
        log.info("Package list: %s", pkgs)

        pkgmgr = get_package_manager(rd, nfsroot)

        tinfoil.logger.setLevel(log.getEffectiveLevel())

        log.info("Update from package feeds")
        pkgmgr.update()
        #log.info("Removing packages")
        #pkgmgr.remove(pkgs)

        # determine high level packages to add
        to_install = []
        installed_pkgs = pkgmgr.list_installed()
        for pkg in pkgs:
            if pkg not in installed_pkgs:
                to_install.append(pkg)

        log.info("Installing new packages...")
        if to_install:
            log.info(f"Packages to install: {to_install}.")
            pkgmgr.install(pkgs)
        else:
            log.info("No packages to install.")

        log.info("Upgrading packages...")
        upgrade(pkgmgr)

        write_stamp_file(nfsroot)
        log.info("Updating nfsroot done.")


def update_package_index():
    import bb.tinfoil

    with bb.tinfoil.Tinfoil() as tinfoil:
        tinfoil.prepare(quiet=1)

        # set to prevent recursive server calls
        tinfoil.config_data.setVar("NFS_UPDATER_INTERNAL", "1")

        log.info("Updating package index...")

        d = tinfoil.config_data
        generate_index_files(d)

        log.info("Package index updated.")


async def update_nfsroot(rootfs_recipe, nfsroot):
    update_package_index()
    update_packages(rootfs_recipe, nfsroot)
