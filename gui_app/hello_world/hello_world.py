# import tkinter as tk

# def say_hello():
#     print("Hello, World!")

# app = tk.Tk()
# app.title("Hello World App")

# hello_button = tk.Button(app, text="Say Hello", command=say_hello)
# hello_button.pack(pady=20)

# app.mainloop()

import eel
from pathlib import Path

# Initialize Eel with the 'web' folder
eel.init(f'{Path(__file__).parent}/web')


@eel.expose
def say_hello_py(name):
    print(f"Hello from Python, {name}!")
    return f"Hello, {name}! This message is from Python."


# Start the app
if __name__ == "__main__":
    eel.start('index.html', size=(400, 300))  # Launch the HTML file
