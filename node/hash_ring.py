import hashlib


class HashRing:
    """
    Consistent hash ring.
    Each physical node gets VIRTUAL_NODES positions on the ring
    for even distribution.
    """
    VIRTUAL_NODES = 150

    def __init__(self):
        self.ring   = {}   # position → node_name
        self.sorted = []   # sorted list of positions

    def add_node(self, name: str):
        """Add a node with VIRTUAL_NODES positions on the ring."""
        for i in range(self.VIRTUAL_NODES):
            key = self._hash(f"{name}:{i}")
            self.ring[key] = name
        self.sorted = sorted(self.ring.keys())

    def remove_node(self, name: str):
        """Remove all virtual nodes for a physical node."""
        for i in range(self.VIRTUAL_NODES):
            key = self._hash(f"{name}:{i}")
            self.ring.pop(key, None)
        self.sorted = sorted(self.ring.keys())

    def get_node(self, key: str) -> str:
        """
        Find which node owns this key.
        Hash the key → find its position on ring →
        walk clockwise to the nearest node.
        """
        if not self.ring:
            raise ValueError("Hash ring is empty — no nodes added")
        pos = self._hash(key)
        for ring_pos in self.sorted:
            if pos <= ring_pos:
                return self.ring[ring_pos]
        # Wrap around — key is past last node, goes to first
        return self.ring[self.sorted[0]]

    def _hash(self, value: str) -> int:
        """MD5 hash → integer position on ring."""
        h = hashlib.md5(value.encode()).hexdigest()
        return int(h, 16)
