// Function to send the name to Python and get a response
function sayHello() {
    const name = document.getElementById("nameInput").value;
    eel.say_hello_py(name)(function(response) {
        document.getElementById("response").innerText = response;
    }).catch(error => {
        console.error("Error calling Python function:", error);
    });
}
