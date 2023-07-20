# poky-nfsroot

Example steps to use:
```
echo 'INHERIT += "nfsroot"' >> $BUILDDIR/conf/local.conf
echo 'IMAGE_FSTYPES:append = " tar.gz"' >> $BUILDDIR/conf/local.conf
bitbake meta-ide-support
bitbake my-rootfs-image
nfsroot=$BUILDDIR/my-nfsroot
runqemu-extract-sdk build/tmp/deploy/images/machine/my-rootfs-image-machine.tar.gz $nfsroot
mkdir scripts/lib/bin  # HACK, because pseudo wrappers will be installed there FIXME
nfs-export-updater --debug my-rootfs-image $nfsroot
```

This directory can now be exported via a userspace NFS server sharing the pseudo
database, so user permissions appear correctly on the device-under-test:

- To start a userspace nfs server: `runqemu-export-rootfs start $nfsroot`
- For QEMU you can also use `runqemu qemux86-64 nographic slirp $nfsroot`

To update the nfsroot, it's sufficient to just build the recipe in question.
To copy files into the nfsroot, use `nfs-cp`, e.g.
`nfs-cp ~/nfsroot/myboard fstab /etc/fstab`.
