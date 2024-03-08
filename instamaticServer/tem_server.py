import datetime
import queue
import socket
import threading
import signal
import traceback
import logging

from TEMController.microscope import Microscope
from serializer import dumper, loader
from utils.config import config

condition = threading.Condition()
stop_program_event = threading.Event()

box = []

_conf = config()
HOST = _conf.default_settings['tem_server_host']
PORT = _conf.default_settings['tem_server_port']
BUFSIZE = 1024


class TemServer(threading.Thread):
    """TEM communcation server.

    Takes a logger object `log`, command queue `q`, and name of the
    microscope `name` that is used to initialize the connection to the
    microscope. Start the server using `TemServer.run` which will wait
    for items to appear on `q` and execute them on the specified
    microscope instance.
    """
    
    def __init__(self, log=None, q=None, name=None):
        super().__init__()

        self._log = log
        self._q = q

        # self.name is a reserved parameter for threads
        self._name = name

        self.verbose = False

    def run(self):
        """Start the server thread."""
        self.tem = Microscope(name=self._name)
        self._name = self.tem.name
        print("Initialized connection to microscope: %s" % (self._name))

        while True:
            now = datetime.datetime.now().strftime('%H:%M:%S.%f')

            cmd = self._q.get()

            with condition:
                func_name = cmd['func_name']
                args = cmd.get('args', ())
                kwargs = cmd.get('kwargs', {})

                try:
                    ret = self.evaluate(func_name, args, kwargs)
                    status = 200
                except Exception as e:
                    traceback.print_exc()
                    if self._log:
                        self._log.exception(e)
                    ret = (e.__class__.__name__, e.args)
                    status = 500

                box.append((status, ret))
                condition.notify()
                print("%s  |  %s  %s: %s" % (now, status, func_name, ret))
                 
    def evaluate(self, func_name: str, args: list, kwargs: dict):
        """Evaluate the function `func_name` on `self.tem` and call it with
        `args` and `kwargs`."""
        print(func_name, args, kwargs)
        f = getattr(self.tem, func_name)
        ret = f(*args, **kwargs)
        return ret

def handle(conn, q):
    """Handle incoming connection, put command on the Queue `q`, which is then
    handled by TEMServer."""
    with conn:
        while True:
            if stop_program_event.is_set():
                break
            
            data = conn.recv(BUFSIZE)
            if not data:
                break

            data = loader(data)
            
            if data == 'exit':
                break

            if data == 'kill':
                break

            with condition:
                q.put(data)
                condition.wait()
                response = box.pop()
                conn.send(dumper(response))


def handle_kb_interrupt(sig, frame):
    stop_program_event.set()


def main():

    import argparse
    description = """
Connects to the TEM and starts a server for microscope communication. Opens a socket on port {HOST}:{PORT}.

This program initializes a connection to the TEM as defined in the config. The purpose of this program is to isolate the microscope connection in a separate process for improved stability of the interface in case instamatic crashes or is started and stopped frequently. For running the GUI, the temserver is required. Another reason is that it allows for remote connections from different PCs. The connection goes over a TCP socket.

The host and port are defined in `config/settings.yaml`.

The data sent over the socket is a serialized dictionary with the following elements:

- `func_name`: Name of the function to call (str)
- `args`: (Optional) List of arguments for the function (list)
- `kwargs`: (Optiona) Dictionary of keyword arguments for the function (dict)

The response is returned as a serialized object.
"""
    
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('-t', '--microscope', action='store', dest='microscope',
                        help="""Override microscope to use.""")

    parser.set_defaults(microscope=None)
    options = parser.parse_args()
    microscope = options.microscope

    logging.basicConfig(filename='tem_server.log', level=logging.INFO)

    q = queue.Queue(maxsize=100)

    tem_reader = TemServer(name=microscope, log=None, q=q)
    tem_reader.start()
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen(0)

    logging.info("Server listening on %s:%s" % (HOST, PORT))
    print ("Server listening on %s:%s" % (HOST, PORT))

    signal.signal(signal.SIGINT, handle_kb_interrupt)
    
    with s:
        while True:
            conn, addr = s.accept()
            #logging.info('Connected by %s' % (addr))
#            print('Connected by', addr)
            command_thread = threading.Thread(target=handle, args=(conn, q))
            command_thread.start()
            command_thread.join()



if __name__ == '__main__':
    main()
