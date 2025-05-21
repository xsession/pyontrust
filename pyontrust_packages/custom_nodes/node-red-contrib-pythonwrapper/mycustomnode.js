const { spawn } = require("child_process");

module.exports = function(RED) {
    function MyCustomNode(config) {
        RED.nodes.createNode(this, config);
        const node = this;

        node.on('input', function(msg) {
            const python = spawn('python3', [__dirname + '/script.py']);
            
            let data = '';
            python.stdout.on('data', (chunk) => data += chunk.toString());
            
            python.stderr.on('data', (err) => node.error("Python error: " + err.toString()));
            
            python.on('close', (code) => {
                try {
                    const result = JSON.parse(data);
                    msg.payload = result.payload;
                    node.send(msg);
                } catch (e) {
                    node.error("Failed to parse Python output: " + e.message);
                }
            });

            python.stdin.write(JSON.stringify(msg));
            python.stdin.end();
        });
    }

    RED.nodes.registerType("mycustomnode", MyCustomNode);
};