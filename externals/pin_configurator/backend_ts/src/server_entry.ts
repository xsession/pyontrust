import { createApp } from './server';

function parseArgs(argv: string[]): { host: string; port: number } {
  let host = '127.0.0.1';
  let port = 5100;

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--host' && argv[index + 1]) {
      host = argv[index + 1];
      index += 1;
      continue;
    }
    if (arg === '--port' && argv[index + 1]) {
      port = Number(argv[index + 1]);
      index += 1;
    }
  }

  return { host, port };
}

const { host, port } = parseArgs(process.argv.slice(2));
const app = createApp();

app.listen(port, host, () => {
  process.stdout.write(`Pin Configurator TS backend listening on http://${host}:${port}\n`);
});