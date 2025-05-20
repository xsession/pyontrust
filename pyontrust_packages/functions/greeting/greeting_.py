

class Greeting:
    def __init__(self):
        self.message = 'Hello, World!'

    def greet(self):
        return self.message
    
    
if __name__ == '__main__':
    g = Greeting()
    print(g.greet())