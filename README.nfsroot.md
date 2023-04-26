# poky-nfsroot

Example steps to use:

Prepare your `local.conf`:

```
echo 'INHERIT += "nfsroot"' >> $BUILDDIR/conf/local.conf
echo 'IMAGE_FSTYPES:append = " tar.gz"' >> $BUILDDIR/conf/local.conf
```

Build your rootfs recipe:

```
bitbake my-rootfs-image
```

Export your rootfs:

```
NFSROOT=$BUILDDIR/my-nfsroot
bitbake qemu-helper-native -caddto_recipe_sysroot
runqemu-extract-sdk $BUILDDIR/tmp/deploy/images/<machine>/<my-rootfs-image-machine>.tar.gz $NFSROOT
```

Start the update server:

```
nfs-export-updater --debug my-rootfs-image $NFSROOT
```

This directory can now be exported via a userspace NFS server sharing the pseudo
database, so user permissions appear correctly on the device-under-test:

- To start a userspace nfs server: `runqemu-export-rootfs start $NFSROOT`
- For QEMU you can also use `runqemu qemux86-64 nographic slirp $NFSROOT`

To update the nfsroot, it's sufficient to just build the recipe in question.
To copy files into the nfsroot, use `nfs-cp`, e.g.
`nfs-cp ~/nfsroot/myboard fstab /etc/fstab`.
