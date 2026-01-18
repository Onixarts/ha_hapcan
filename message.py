class HapcanMessage:
    def __init__(self, frame: bytes):
        self.frame = list(frame)
        self.frame_type = (frame[1] << 4) + (frame[2] >> 4)
        self.is_answer = (frame[2] & 0x01) != 0
        self.node = frame[3]
        self.group = frame[4]
        self.length = len(frame)
        self.description_index = None
        
    def __repr__(self):
        return f"<HapcanMessage type=0x{self.frame_type:03X} node={self.node} group={self.group}>"

    def __str__(self):
        return " ".join(f"{b:02X}" for b in self.frame)
