import os
import struct

# Constants
BLOCK_SIZE = 512
MAGIC_NUMBER = b'4337PRJ3'
MAX_KEYS = 19
MAX_CHILDREN = 20

# Helper functions
def to_big_endian(value, length=8):
    return value.to_bytes(length, byteorder='big')

def from_big_endian(bytes_value):
    return int.from_bytes(bytes_value, byteorder='big')

# B-Tree Node
class BTreeNode:
    def __init__(self, block_id, parent_id=0):
        self.block_id = block_id
        self.parent_id = parent_id
        self.num_keys = 0
        self.keys = [0] * MAX_KEYS
        self.values = [0] * MAX_KEYS
        self.children = [0] * MAX_CHILDREN

    def to_bytes(self):
        node_bytes = struct.pack('>Q', self.block_id)
        node_bytes += struct.pack('>Q', self.parent_id)
        node_bytes += struct.pack('>Q', self.num_keys)
        node_bytes += b''.join(to_big_endian(k) for k in self.keys)
        node_bytes += b''.join(to_big_endian(v) for v in self.values)
        node_bytes += b''.join(to_big_endian(c) for c in self.children)
        padding = BLOCK_SIZE - len(node_bytes)
        return node_bytes + (b'\x00' * padding)

    @staticmethod
    def from_bytes(data):
        block_id = from_big_endian(data[:8])
        parent_id = from_big_endian(data[8:16])
        num_keys = from_big_endian(data[16:24])
        keys = [from_big_endian(data[24 + i * 8:32 + i * 8]) for i in range(MAX_KEYS)]
        values = [from_big_endian(data[176 + i * 8:184 + i * 8]) for i in range(MAX_KEYS)]
        children = [from_big_endian(data[328 + i * 8:336 + i * 8]) for i in range(MAX_CHILDREN)]
        node = BTreeNode(block_id, parent_id)
        node.num_keys = num_keys
        node.keys = keys
        node.values = values
        node.children = children
        return node

# Index File Manager
class IndexFileManager:
    def __init__(self):
        self.file = None
        self.root_block_id = 0
        self.next_block_id = 1

    def create(self, filename):
        if os.path.exists(filename):
            overwrite = input(f"{filename} already exists. Overwrite? (yes/no): ").strip().lower()
            if overwrite != 'yes':
                return
        self.file = open(filename, 'wb+')
        self._write_header()
        print(f"Created and opened index file: {filename}")

    def open(self, filename):
        if not os.path.exists(filename):
            print(f"Error: {filename} does not exist.")
            return
        with open(filename, 'rb') as f:
            magic = f.read(8)
            if magic != MAGIC_NUMBER:
                print(f"Error: {filename} is not a valid index file.")
                return
        self.file = open(filename, 'rb+')
        self._read_header()
        print(f"Opened index file: {filename}")

    def _write_header(self):
        self.file.seek(0)
        header = MAGIC_NUMBER + to_big_endian(self.root_block_id) + to_big_endian(self.next_block_id)
        padding = BLOCK_SIZE - len(header)
        self.file.write(header + (b'\x00' * padding))

    def _read_header(self):
        self.file.seek(0)
        header = self.file.read(BLOCK_SIZE)
        if len(header) < BLOCK_SIZE:
            raise ValueError("Invalid header size")
        self.root_block_id = from_big_endian(header[8:16])
        self.next_block_id = from_big_endian(header[16:24])

    def _write_node(self, node):
        if not self.file:
            raise ValueError("No file is open to write nodes.")
        position = node.block_id * BLOCK_SIZE
        self.file.seek(position)
        self.file.write(node.to_bytes())

    def _read_node(self, block_id):
        if not self.file:
            raise ValueError("No file is open to read nodes.")
        position = block_id * BLOCK_SIZE
        self.file.seek(position)
        data = self.file.read(BLOCK_SIZE)
        if len(data) < BLOCK_SIZE:
            raise ValueError(f"Invalid node block size at block ID {block_id}")
        return BTreeNode.from_bytes(data)

    def close(self):
        if self.file:
            self._write_header()
            self.file.close()
            self.file = None

    def insert(self, key, value):
        if self.root_block_id == 0:
            root = BTreeNode(self.next_block_id)
            root.num_keys = 1
            root.keys[0] = key
            root.values[0] = value
            self._write_node(root)
            self.root_block_id = self.next_block_id
            self.next_block_id += 1
            print(f"Inserted ({key}, {value}) into the new root node.")
        else:
            node = self._read_node(self.root_block_id)
            if node.num_keys < MAX_KEYS:
                node.keys[node.num_keys] = key
                node.values[node.num_keys] = value
                node.num_keys += 1
                self._write_node(node)
                print(f"Inserted ({key}, {value}) into node {node.block_id}.")
            else:
                print("Error: Node splitting is not implemented yet.")

    def search(self, key):
        if self.root_block_id == 0:
            print("Error: No index file is open or the tree is empty.")
            return
        node = self._read_node(self.root_block_id)
        while node:
            for i in range(node.num_keys):
                if node.keys[i] == key:
                    print(f"Found key {key} with value {node.values[i]} in node {node.block_id}.")
                    return
            next_node = next((child for child in node.children if child != 0), None)
            if not next_node:
                break
            node = self._read_node(next_node)
        print(f"Key {key} not found.")

    def load(self, filename):
        try:
            with open(filename, 'r') as file:
                for line in file:
                    key, value = map(int, line.strip().split(','))
                    self.insert(key, value)
            print(f"Loaded data from {filename}.")
        except Exception as e:
            print(f"Error loading file {filename}: {e}")

    def print_tree(self):
        if self.root_block_id == 0:
            print("The B-tree is empty.")
            return

        def traverse(node_id, level=0):
            if node_id == 0:
                return
            node = self._read_node(node_id)
            print(f"{'  ' * level}Node {node.block_id}: Keys = {node.keys[:node.num_keys]}, Values = {node.values[:node.num_keys]}")
            for child_id in node.children[:node.num_keys + 1]:
                traverse(child_id, level + 1)

        traverse(self.root_block_id)

    def extract(self, filename):
        if os.path.exists(filename):
            overwrite = input(f"{filename} already exists. Overwrite? (yes/no): ").strip().lower()
            if overwrite != 'yes':
                return
        with open(filename, 'w') as file:
            def traverse(node_id):
                if node_id == 0:
                    return
                node = self._read_node(node_id)
                for i in range(node.num_keys):
                    file.write(f"{node.keys[i]},{node.values[i]}\n")
                for child_id in node.children[:node.num_keys + 1]:
                    traverse(child_id)
            traverse(self.root_block_id)
        print(f"Extracted index data to {filename}.")

# Main Menu
def main():
    manager = IndexFileManager()

    while True:
        print("\nCommands: create, open, insert, search, load, print, extract, quit")
        command = input("Enter command: ").strip().lower()

        if command == "create":
            filename = input("Enter file name: ").strip()
            manager.create(filename)

        elif command == "open":
            filename = input("Enter file name: ").strip()
            manager.open(filename)

        elif command == "insert":
            try:
                key = int(input("Enter key: "))
                value = int(input("Enter value: "))
                manager.insert(key, value)
            except ValueError:
                print("Error: Key and value must be integers.")

        elif command == "search":
            try:
                key = int(input("Enter key: "))
                manager.search(key)
            except ValueError:
                print("Error: Key must be an integer.")

        elif command == "load":
            filename = input("Enter file name to load: ").strip()
            manager.load(filename)

        elif command == "print":
            manager.print_tree()

        elif command == "extract":
            filename = input("Enter file name to extract: ").strip()
            manager.extract(filename)

        elif command == "quit":
            manager.close()
            print("Exiting program.")
            break

        else:
            print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()
