import { createInterface } from 'node:readline';
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
import { writeFile, mkdir } from 'node:fs/promises';
import { credentialEncryption } from './windows-encryption.mjs';

const runtimeRoot = process.env.GPTR_RUNTIME ?? 'D:/Applications/GPTResearcher';
const dataRoot = process.env.GPTR_DATA ?? 'D:/AppData/GPTResearcher';
const sdk = join(runtimeRoot, 'siwc/node_modules/@siwc/local/dist/index.js');
const { createChatGPT } = await import(pathToFileURL(sdk).href);
const storageDir = join(dataRoot, 'chatgpt');
const client = createChatGPT({
  appName: 'GPT Researcher', appId: 'gpt-researcher', storageDir,
  redirectPort: 0, sendHostId: true, credentialEncryption,
  openBrowser: async url => {
    await writeFile(join(storageDir, 'authorization-url.txt'), url, { mode: 0o600 });
    process.stderr.write(`Open the authorization URL saved in ${join(storageDir, 'authorization-url.txt')}\n`);
  },
});

const safeError = error => error.toJSON?.() ?? { code: 'local_runtime_error', message: 'The local ChatGPT runtime failed.' };
async function respond(request) {
  if (!request || !Number.isInteger(request.id)) throw new Error('Invalid request');
  if (request.op === 'status') {
    const session = await client.getSession();
    return { status: session.status, sharing: session.sharing, error: session.error };
  }
  if (request.op === 'models') return await client.listModels();
  if (request.op !== 'respond') throw new Error('Unsupported operation');
  if (!Array.isArray(request.messages) || request.messages.length > 200) throw new Error('Invalid messages');
  const input = request.messages.map(message => {
    if (!['user', 'assistant', 'developer', 'system'].includes(message.role) || typeof message.content !== 'string') {
      throw new Error('Unsupported message');
    }
    return { role: message.role === 'system' ? 'developer' : message.role, content: message.content };
  });
  const started = Date.now();
  process.stderr.write(`[ChatGPT plan] request ${request.id} started\n`);
  const result = await client.streamResponse({ model: request.model, input });
  process.stderr.write(`[ChatGPT plan] request ${request.id} completed in ${Math.round((Date.now() - started) / 1000)}s\n`);
  return { text: result.text, completed: true, billing: 'chatgpt-plan' };
}

if (process.argv[2] === 'signin') {
  try {
    const session = await client.signIn();
    console.log(JSON.stringify({ status: session.status, sharing: session.sharing }));
  } catch (error) { console.error(JSON.stringify(safeError(error))); process.exitCode = 1; }
} else {
  // Private child-process pipes carry text and results; account credentials stay inside the official SDK.
  const lines = createInterface({ input: process.stdin, crlfDelay: Infinity });
  for await (const line of lines) {
    let request;
    try {
      if (line.length > 4 * 1024 * 1024) throw new Error('Request too large');
      request = JSON.parse(line);
      const result = await respond(request);
      process.stdout.write(`${JSON.stringify({ id: request.id, result })}\n`);
    } catch (error) {
      process.stdout.write(`${JSON.stringify({ id: request?.id, error: safeError(error) })}\n`);
    }
  }
}
