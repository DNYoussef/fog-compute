import { spawn } from 'child_process';

type ProcessStreamOptions = {
  command: string;
  args: string[];
  cwd: string;
  env?: NodeJS.ProcessEnv;
  initialOutput: string[];
  completionOutput: (code: number | null) => string;
  errorOutput: (error: Error) => string;
};

export function createProcessStream({
  command,
  args,
  cwd,
  env,
  initialOutput,
  completionOutput,
  errorOutput,
}: ProcessStreamOptions) {
  const encoder = new TextEncoder();
  let closed = false;
  let controllerRef: ReadableStreamDefaultController<Uint8Array> | null = null;
  let proc: ReturnType<typeof spawn> | null = null;

  const closeProcess = () => {
    if (proc && !proc.killed) {
      proc.kill();
    }
  };

  const write = (text: string) => {
    if (closed || !controllerRef) {
      return;
    }

    try {
      controllerRef.enqueue(encoder.encode(text));
    } catch {
      closed = true;
      closeProcess();
    }
  };

  const finish = (text: string) => {
    if (closed) {
      return;
    }

    write(text);
    closed = true;

    try {
      controllerRef?.close();
    } catch {
      // The client may have cancelled the stream between the final write and close.
    }
  };

  return new ReadableStream<Uint8Array>({
    start(controller) {
      controllerRef = controller;
      initialOutput.forEach(write);

      proc = spawn(command, args, {
        cwd,
        shell: true,
        stdio: ['ignore', 'pipe', 'pipe'],
        env,
      });

      proc.stdout?.on('data', (data) => {
        write(data.toString());
      });

      proc.stderr?.on('data', (data) => {
        write(data.toString());
      });

      proc.once('close', (code) => {
        finish(completionOutput(code));
      });

      proc.once('error', (error) => {
        finish(errorOutput(error));
      });
    },
    cancel() {
      closed = true;
      closeProcess();
    },
  });
}
