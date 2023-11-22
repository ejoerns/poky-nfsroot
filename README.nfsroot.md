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

Start the update server:

```
nfs-export-updater --debug my-rootfs-image <exportdir>
```

This will

- extract the rootfs tar archive to the folder `<exportdir>` if this does not exist yet.
  If the argument is omitted, the default folder name `nfsroot-<image>-${MACHINE}` will be used instead.
- start a unfsd instance on this folder

To update the nfsroot, it's sufficient to just build the recipe in question.
To copy files into the nfsroot, use `nfs-cp`, e.g.
`nfs-cp ~/nfsroot/myboard fstab /etc/fstab`.
