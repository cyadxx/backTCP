import os
import socket
import time
import threading

from utils import log


class BTcpConnection:
    def __init__(self, mode, addr, port):
        # Create a TCP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn = None
        self.remote_addr = None

        if mode == 'send':
            self.remote_addr = addr, port
            self.sock.connect(self.remote_addr)
            self.conn = self.sock

        elif mode == 'recv':
            self.sock.bind((addr, port))
            log('info', f"Listening on {addr} port {port}")
            self.sock.listen(1)
            self.conn, self.remote_addr = self.sock.accept()
            log('info', f"Accepted connection from {self.remote_addr[0]} port {self.remote_addr[1]}")
        else:
            raise ValueError(f"Unexpected mode {mode}")

    def __del__(self):
        self.close()

    def close(self):
        try:
            #self.conn.shutdown(socket.SHUT_RDWR)
            self.conn.close()
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass
        # set them to None so other code knows
        self.conn = None
        self.sock = None

    def settimeout(self, timeout):
        self.sock.settimeout(timeout)

    def send(self, packet):
        if packet is None:
            packet = b''
        self.conn.sendall(bytes(packet))

    #def recv(self, size=None):
    #    return BTcpPacket.from_bytes(self.conn.recv(size or (7 + 64)))
    
    def recv(self):
        return BTcpPacket.from_bytes(self.conn.recv(7 + 64))



class BTcpPacket:
    def __init__(self, sport=0, dport=0, seq=0, ack=0, data_off=0, win_size=0, flag=0, data=b""):
        self.sport = sport
        self.dport = dport
        self.seq = seq
        self.ack = ack
        self.data_off = data_off
        self.win_size = win_size
        self.flag = flag
        self.data = data

    def regulate(self):
        # Make sure the values don't stir up
        self.seq &= 0xFF
        self.ack &= 0xFF
        self.data_off &= 0xFF
        self.win_size &= 0xFF
        self.flag &= 1  # Could be 0xFF, but we only need "retransmission" flag

    def __bytes__(self):
        self.regulate()
        return bytes([
            self.sport, self.dport, self.seq, self.ack,
            self.data_off, self.win_size, self.flag,
        ]) + bytes(self.data)

    @staticmethod
    def from_bytes(data):
        if not data:
            return None
        return BTcpPacket(
            sport=data[0], dport=data[1], seq=data[2], ack=data[3],
            data_off=data[4], win_size=data[5], flag=data[6], data=data[7:]
        )

    def __repr__(self):
        if len(self.data) > 1:
            s = f"<{len(self.data)} bytes>"
        elif len(self.data) == 0:
            s = "<empty>"
        else:
            s = "<1 byte>"
        return f"BTcpPacket(seq={self.seq}, ack={self.ack}, win_size={self.win_size}, flag={self.flag}, data={s})"


def recvForSend(conn, totalPkts, all):
    # another thread for send
    # recv ack pkts and move the window
    
    while all['base'] < totalPkts:
        p = conn.recv()
        if p and p.ack == all['base'] & 0xff:
            log('info', f"RECV ack {p.ack} when base is {all['base']}")
            all['base'] += 1
            if all['base'] == all['nextSeqNum']:
                all['isTimerStop'] = 1
            else:
                all['time'] = time.time()
                all['isTimerStop'] = 0


def send(data, addr, port):
    conn = BTcpConnection('send', addr, port)

    N = 5           # window size

    chunks = [data[x * 64:x * 64 + 64] for x in range((len(data) - 1) // 64 + 1)]
    packets = [BTcpPacket(seq=i & 0xFF, data_off=7, win_size=N, data=chunk) for i, chunk in enumerate(chunks)]
    totalPkts = len(packets)

    # TODO: "data" is a bytes object
    #       You should split it up into BTcpPacket objects, and call conn.send(pkt) on each one
    # Example: > p = BTcpPacket(data=b"hello")
    #          > conn.send(p)

    # TODO: Delete the following code and add your own

    # N = 5
    # time = 0
    # base = 0
    # nextSeqNum = 0
    all = {'base': 0, 'nextSeqNum': 0, 'time': 0, 'isTimerStop': 0}

    thread = threading.Thread(target=recvForSend, args=(conn, totalPkts, all))
    thread.start()

    while all['base'] < totalPkts:
        if((all['nextSeqNum'] < all['base'] + N) and (all['nextSeqNum'] < totalPkts)):
            log('info', f"SEND pkt {packets[all['nextSeqNum']]}")
            conn.send(packets[all['nextSeqNum']])
            if all['base'] == all['nextSeqNum']:
                all['time'] = time.time()
                all['isTimerStop'] = 0
            all['nextSeqNum'] += 1
        if(time.time() - all['time'] > 0.010 and all['isTimerStop'] == 0):
            # timeout for pkt base
            log('info', f"TIMEOUT for pkt {all['base']}")
            for i in range(all['base'], all['nextSeqNum']):
                packets[i].flag = 1
            all['nextSeqNum'] = all['base']
            all['isTimerStop'] = 1
    return
'''
            all['time'] = time.time()
            all['isTimerStop'] = 0
            for i in range(all['base'], all['nextSeqNum']):
                packets[i].flag = 1
                conn.send(packets[i])
                log('info', f"RESEND pkt {packets[i]}")
'''
    # End of your own code
    # return


def recv(addr, port):
    conn = BTcpConnection('recv', addr, port)

    data = b''  # Nothing received yet

    # TODO: Call conn.recv to receive packets
    #       Received packets are of class BTcpPacket, so you can access packet information and content easily
    # Example: > p = conn.recv()
    #          Now p.seq, p.ack, p.data (and everything else) are available

    # TODO: Assemble received binary data into `data` variable.
    #       Make sure you're handling disorder and timeouts properly

    expectSeqNum = 0        # packet seq begin with 0


    while True:
        p = conn.recv()
        if p is not None:
            log('info', 'RECV packet: {} when expectSeqNum is {} \n and the data is{}'.format(p, expectSeqNum, p.data))
        if p is None:  # No more packets
            break
        
        if p.seq == expectSeqNum:
            data += p.data
            sndpkt = BTcpPacket(ack=expectSeqNum, flag=1, data=b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
            conn.send(sndpkt)
            log('info', f"SEND ACK pkt {sndpkt}")
            expectSeqNum = (expectSeqNum + 1) & 0xff
            log('info', 'expectSeqNum becomes {}'.format(expectSeqNum))
        else:
            conn.send(BTcpPacket(ack=expectSeqNum-1, flag=1, data=b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"))

    # End of your own code

    return data






'''
def send(data, addr, port):
    conn = BTcpConnection('send', addr, port)

    N = 5

    chunks = [data[x * 64:x * 64 + 64] for x in range((len(data) - 1) // 64 + 1)]
    packets = [BTcpPacket(seq=i & 0xFF, data_off=7, win_size=N, data=chunk) for i, chunk in enumerate(chunks)]
    total = len(packets)

    # TODO: "data" is a bytes object
    #       You should split it up into BTcpPacket objects, and call conn.send(pkt) on each one
    # Example: > p = BTcpPacket(data=b"hello")
    #          > conn.send(p)

    # TODO: Delete the following code and add your own

    # N = 5
    base = 0
    nextSeqNum = 0

    # send N pkt first
    # fulfill the window
    for i in range(N):
        conn.send(packets[nextSeqNum])
        log('info', f"SEND packet {packets[nextSeqNum]}")
        nextSeqNum += 1

    conn.settimeout(0.01)
    while True:
        try:
            p = conn.recv()
        except socket.timeout:
            # the base pkt is timeout
            # resend all pkts in the window
            log('info', f"TIMEOUT for packet {packets[base]}")
            for i in range(N):
                if base + i < total:
                    packets[base + i].flag = 1
                    log('info', f"RESEND packet {packets[base + i]}")
                    conn.send(packets[base + i])
        else:
            # recv an ack pkt
            # if ack == base
            #   base++ & send one pkt 
            # if ack == base - 1
            #   do nothing

            distance = (p.ack + 256 - base % 256) % 256
            log('info', 'Distance is {}'.format(distance))
            if distance >= 0 and distance < N:
                log('info', f"RECV ack packet {p.ack} when base is {base}")
                if p.ack == base & 0xff:
                    base += 1
                    if base >= total:
                        break
                    while nextSeqNum < total & nextSeqNum < base + N:
                        log('info', f"SEND packet {packets[nextSeqNum]}")
                        conn.send(packets[nextSeqNum])
                        nextSeqNum += 1

    # End of your own code
    return

def recv(addr, port):
    conn = BTcpConnection('recv', addr, port)

    data = b''  # Nothing received yet

    # TODO: Call conn.recv to receive packets
    #       Received packets are of class BTcpPacket, so you can access packet information and content easily
    # Example: > p = conn.recv()
    #          Now p.seq, p.ack, p.data (and everything else) are available

    # TODO: Assemble received binary data into `data` variable.
    #       Make sure you're handling disorder and timeouts properly

    expectSeqNum = 0        # packet seq begin with 0

    conn.settimeout(0.010)  # 10ms timeout
    while True:
        p = conn.recv()
        log('info', 'RECV packet: {} when expectSeqNum is {}'.format(p, expectSeqNum))
        if p is None:  # No more packets
            break
        
        if p.seq == expectSeqNum:
            data += p.data
            sndpkt = BTcpPacket(ack=expectSeqNum, flag=1)
            conn.send(sndpkt)
            expectSeqNum = (expectSeqNum + 1) & 0xff
            log('info', 'expectSeqNum becomes {}'.format(expectSeqNum))
        else:
            conn.send(BTcpPacket(ack=expectSeqNum-1, flag=1))

    # End of your own code

    return data
'''