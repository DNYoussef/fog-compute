import { NextRequest } from 'next/server';
import { join } from 'path';
import { createProcessStream } from '../_lib/process-stream';

export async function POST(request: NextRequest) {
  try {
    const { suite } = await request.json();
    const projectRoot = join(process.cwd(), '..', '..');

    let command: string;
    let args: string[];
    let cwd: string = projectRoot;

    // Determine which test suite to run
    switch (suite) {
      case 'rust':
        command = 'cargo';
        args = ['test', '--all', '--', '--test-threads=1'];
        break;
      case 'python':
        command = 'python';
        args = ['-m', 'pytest', 'tests/', '-v', '--tb=short'];
        cwd = join(projectRoot, 'backend');
        break;
      case 'all':
        command = 'python';
        args = ['-m', 'pytest', 'tests/', '-v', '--tb=short'];
        cwd = join(projectRoot, 'backend');
        break;
      default:
        return new Response('Invalid test suite\n', {
          status: 400,
          headers: { 'Content-Type': 'text/plain; charset=utf-8' },
        });
    }

    const stream = createProcessStream({
      command,
      args,
      cwd,
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
      initialOutput: [
        `Running ${suite} tests...\n`,
        `Command: ${command} ${args.join(' ')}\n`,
        `Working directory: ${cwd}\n\n`,
      ],
      completionOutput: (code) => `\n\nTests completed with exit code: ${code}\n`,
      errorOutput: (error) => `\n\nError running tests: ${error.message}\n`,
    });

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
        'Transfer-Encoding': 'chunked',
      },
    });
  } catch (error) {
    return new Response(`Error: ${error}`, {
      status: 500,
      headers: { 'Content-Type': 'text/plain' },
    });
  }
}
