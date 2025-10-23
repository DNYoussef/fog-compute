import { spawn } from 'child_process';
import { join } from 'path';

export async function POST() {
  try {
    const projectRoot = join(process.cwd(), '..', '..');
    const benchmarkScript = join(projectRoot, 'scripts', 'benchmark_comprehensive.py');

    // Create a readable stream for the response
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        controller.enqueue(encoder.encode('Starting comprehensive benchmark suite...\n'));
        controller.enqueue(encoder.encode(`Script: ${benchmarkScript}\n\n`));

        const proc = spawn('python', [benchmarkScript], {
          cwd: projectRoot,
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
            encoder.encode(`\n\nBenchmarks completed with exit code: ${code}\n`)
          );
          if (code === 0) {
            controller.enqueue(
              encoder.encode('Results saved to benchmark_results.json\n')
            );
          }
          controller.close();
        });

        proc.on('error', (error) => {
          controller.enqueue(
            encoder.encode(`\n\nError running benchmarks: ${error.message}\n`)
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
