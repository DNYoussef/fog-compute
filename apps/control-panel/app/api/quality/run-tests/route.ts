import { NextRequest } from 'next/server';
import { spawn } from 'child_process';
import { join } from 'path';

export async function POST(request: NextRequest) {
  try {
    const { suite } = await request.json();
    const projectRoot = join(process.cwd(), '..', '..');

    // Create a readable stream for the response
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
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
            controller.enqueue(encoder.encode('Invalid test suite\n'));
            controller.close();
            return;
        }

        controller.enqueue(encoder.encode(`Running ${suite} tests...\n`));
        controller.enqueue(encoder.encode(`Command: ${command} ${args.join(' ')}\n`));
        controller.enqueue(encoder.encode(`Working directory: ${cwd}\n\n`));

        const proc = spawn(command, args, {
          cwd,
          shell: true,
          env: { ...process.env, PYTHONUNBUFFERED: '1' },
        });

        proc.stdout.on('data', (data) => {
          controller.enqueue(encoder.encode(data.toString()));
        });

        proc.stderr.on('data', (data) => {
          controller.enqueue(encoder.encode(data.toString()));
        });

        proc.on('close', (code) => {
          controller.enqueue(
            encoder.encode(`\n\nTests completed with exit code: ${code}\n`)
          );
          controller.close();
        });

        proc.on('error', (error) => {
          controller.enqueue(
            encoder.encode(`\n\nError running tests: ${error.message}\n`)
          );
          controller.close();
        });
      },
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
