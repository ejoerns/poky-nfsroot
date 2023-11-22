import asyncio
import os
import logging

from .pkgindex import update_nfsroot
from .pkgindex import prepare_native_tools

log = logging.getLogger('nfs-export-updater')


class NFSRootUpdateServer():
    def __init__(self, rootfs_recipe, nfsroot_dir):
        self.rootfs_recipe = rootfs_recipe
        self.nfsroot_dir = nfsroot_dir

    async def handle_client(self, reader, writer):
        is_handling_request = False

        while True:
            # Receive data from the client
            data = await reader.read(1024)
            if not data:
                break

            message = data.decode()
            print("Received data:", message)

            if message == "bitbake_done":
                if is_handling_request:
                    print("Already handling a request, ignoring...")
                else:
                    is_handling_request = True
                    print("Handling 'bitbake_done'")
                    # Needs to be handled async because bitbake needs to terminate
                    # itself first
                    asyncio.create_task(update_nfsroot(self.rootfs_recipe, self.nfsroot_dir))
            else:
                print(f"Got unexpected message: {message}")

            print("Sending respone...")
            # Process the data (replace with your own logic)
            response = "Server received: " + message

            # Send a response back to the client
            writer.write(response.encode())
            await writer.drain()

            if is_handling_request:
                break

        print("Client disconnected")
        writer.close()

    async def start_server(self, sock_instance):
        log.info("Prepare native tools")
        prepare_native_tools()

        # Set the path for the Unix domain socket
        socket_path = f"/tmp/nfsup-{os.environ['USER']}-{sock_instance}.sock"

        # Remove the socket file if it already exists
        if os.path.exists(socket_path):
            log.info(f"Removing existing socket path {socket_path}")
            os.remove(socket_path)

        server = await asyncio.start_unix_server(self.handle_client, path=socket_path)
        log.info(f"Server is running on {socket_path}")

        async with server:
            await server.serve_forever()
