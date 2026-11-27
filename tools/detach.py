"""Start a command fully detached: no console, its own process group (no Ctrl+C reaches it), out of the caller's job.
usage: python tools/detach.py LOG CWD CMD...  (stdout and stderr appended to LOG; prints the pid). 11-27: a job
started with Start-Process + cmd /c, or from a tool call, can die when its console or job goes; this one cannot."""
import subprocess
import sys

log, cwd, cmd = sys.argv[1], sys.argv[2], sys.argv[3:]
flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | 0x01000000  # CREATE_BREAKAWAY_FROM_JOB
fh = open(log, "ab")
try:
    p = subprocess.Popen(cmd, cwd=cwd, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         creationflags=flags, close_fds=True)
except OSError:   # the job forbids breakaway
    p = subprocess.Popen(cmd, cwd=cwd, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         creationflags=flags & ~0x01000000, close_fds=True)
print(p.pid)
