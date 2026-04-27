import time

class Cache:
    def __init__(self, ttl):
        self.ttl = ttl
        self.cache = {}
    
    def set(self, key, value, priority: int = 0):
        self.cache[key] = {'value': value, 'time': time.time(), 'priority': priority}
    
    def get(self, key):
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry['time'] < self.ttl:
                return entry['value']
            else:
                del self.cache[key]
        return None
    
    def get_cached_time_by_key(self, key):
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry['time'] < self.ttl:
                return entry['time']
            else:
                del self.cache[key]
        return None
    
    def get_priority_by_key(self, key):
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry['time'] < self.ttl:
                return entry['priority']
            else:
                del self.cache[key]
        return -1
    
    def get_all(self):
        return self.cache
    
    def get_count(self):
        return len(self.cache)
    
    def get_front(self):
        return self.cache[0] if len(self.cache) > 0 else None
    
    def get_rear(self):
        return self.cache[len(self.cache)-1] if len(self.cache) > 0 else None
    
    def clear(self):
        self.cache = {}
        return True