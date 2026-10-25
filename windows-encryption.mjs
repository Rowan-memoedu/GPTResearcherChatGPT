import { spawn } from 'node:child_process';

const script = `$ErrorActionPreference='Stop';
$payload=[Console]::In.ReadToEnd() | ConvertFrom-Json;
$bytes=[Convert]::FromBase64String($payload.data);
$entropy=[Text.Encoding]::UTF8.GetBytes('gpt-researcher-chatgpt-v1');
if($payload.operation -eq 'encrypt') {
  $result=[Security.Cryptography.ProtectedData]::Protect($bytes,$entropy,[Security.Cryptography.DataProtectionScope]::CurrentUser)
} elseif($payload.operation -eq 'decrypt') {
  $result=[Security.Cryptography.ProtectedData]::Unprotect($bytes,$entropy,[Security.Cryptography.DataProtectionScope]::CurrentUser)
} else { throw 'Unsupported operation' };
[Console]::Out.Write([Convert]::ToBase64String($result));`;

async function transform(operation, bytes) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.env.GPTR_PWSH ?? 'pwsh', ['-NoLogo', '-NoProfile', '-NonInteractive', '-Command', script], {
      windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'],
    });
    let output = '';
    const timer = setTimeout(() => { child.kill(); reject(new Error('DPAPI operation timed out')); }, 15000);
    child.stdout.on('data', chunk => { output += chunk.toString(); });
    child.stderr.resume();
    child.on('error', () => { clearTimeout(timer); reject(new Error('DPAPI helper could not start')); });
    child.on('close', code => {
      clearTimeout(timer);
      if (code !== 0) return reject(new Error('DPAPI operation failed'));
      resolve(Buffer.from(output.trim(), 'base64'));
    });
    child.stdin.end(JSON.stringify({ operation, data: Buffer.from(bytes).toString('base64') }));
  });
}

export const credentialEncryption = {
  id: 'windows-dpapi-current-user-gptr-v1',
  isAvailable: () => process.platform === 'win32',
  encrypt: text => transform('encrypt', Buffer.from(text, 'utf8')),
  decrypt: async bytes => (await transform('decrypt', bytes)).toString('utf8'),
};
