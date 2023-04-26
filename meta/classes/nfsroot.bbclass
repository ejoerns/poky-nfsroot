python nfsroot_eventhandler() {
    import socket
    import os

    # Set the path for the Unix socket
    socket_path = '/tmp/nfsup.sock'
    
    # NFS_UPDATER_INTERNAL is set by nfs-root-updater to prevent calling itself
    carainer_internal = d.getVar('NFS_UPDATER_INTERNAL')

    # prevent from self-calling
    if not carainer_internal:

        # Create the Unix socket client
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        try:
            # Connect to the server
            client.connect(socket_path)
        except ConnectionRefusedError or FileNotFoundError:
            bb.warn('Cannot connect to nfs-root-updater server, skipping update of nfsroot')
            client.close()
            return

        bb.note(f'Notifying nfs-root-updater server..')
        # Send a message to the server
        message = 'bitbake_done'
        client.sendall(message.encode())

        # Receive a response from the server
        response = client.recv(1024)
        bb.note(f'Received response: {response.decode()}')

        # Close the connection
        client.close()
}

addhandler nfsroot_eventhandler
nfsroot_eventhandler[eventmask] = "bb.event.BuildCompleted"

# we rely on package-management information in the generated rootfs
IMAGE_FEATURES += "package-management"
# The PR server should be running to generate new packages on changes
PRSERV_HOST ?= "localhost:0"
