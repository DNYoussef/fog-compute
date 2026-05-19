import { join } from 'path';
import { createProcessStream } from '../_lib/process-stream';

export async function POST() {
  try {
    const projectRoot = join(process.cwd(), '..', '..');
    const benchmarkScript = join(projectRoot, 'scripts', 'benchmark_comprehensive.py');

    const stream = createProcessStream({
      command: 'python',
      args: [benchmarkScript],
      cwd: projectRoot,
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
      initialOutput: [
        'Starting comprehensive benchmark suite...\n',
        `Script: ${benchmarkScript}\n\n`,
      ],
      completionOutput: (code) => {
        const output = `\n\nBenchmarks completed with exit code: ${code}\n`;
        return code === 0 ? `${output}Results saved to benchmark_results.json\n` : output;
      },
      errorOutput: (error) => `\n\nError running benchmarks: ${error.message}\n`,
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
