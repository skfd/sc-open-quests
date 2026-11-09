"""Read an engine task trace (-Dopenquests.taskTrace=<file>, engine/README.md): per city, is the area pass
held by one run or by the CPU? Args: trace.tsv [threads=24]"""
import sys, collections
rows = collections.defaultdict(list)
for l in open(sys.argv[1], encoding='utf-8'):
    city, label, thread, s, e, cpu = l.rstrip('\n').split('\t')
    rows[city].append((label, thread, float(s), float(e), float(cpu)))
T = int(sys.argv[2]) if len(sys.argv) > 2 else 24
for city, rs in rows.items():
    runs = [r for r in rs if not r[0].startswith('(tally)')]
    tallies = [r for r in rs if r[0].startswith('(tally)')]
    wall = max(r[3] for r in runs)
    busy = sum(r[3] - r[2] for r in runs); cpu = sum(r[4] for r in runs)
    print(f'== {city}: {len(runs)} runs, run phase {wall:.1f} s, busy {busy:.0f} thread-s, CPU {cpu:.0f} s')
    print(f'   threads busy on average {busy / wall:.1f} of {T}; CPU {cpu / wall:.1f} cores; CPU/busy {cpu / busy:.0%}')
    print(f'   lower bound if perfectly spread: {cpu / T:.1f} s; longest run {max(r[3] - r[2] for r in runs):.1f} s')
    if tallies:
        tw = max(r[3] for r in tallies) - min(r[2] for r in tallies)
        print(f'   tally phase {tw:.1f} s, CPU {sum(r[4] for r in tallies):.0f} s')
    # busy threads per second
    line = []
    for sec in range(int(wall) + 1):
        b = sum(max(0, min(r[3], sec + 1) - max(r[2], sec)) for r in runs)
        line.append(b)
    print('   busy threads by second: ' + ' '.join(f'{b:.0f}' for b in line))
    tail = [r for r in runs if r[3] > wall - 0.25 * wall]
    print('   still running in the last quarter:')
    for r in sorted(tail, key=lambda r: -r[3])[:12]:
        print(f'     {r[0]:<42} {r[2]:6.1f}-{r[3]:6.1f} s  cpu {r[4]:5.1f}')
    print('   longest runs:')
    for r in sorted(runs, key=lambda r: r[2] - r[3])[:15]:
        print(f'     {r[0]:<42} {r[3] - r[2]:6.1f} s  start {r[2]:5.1f}  cpu {r[4]:5.1f}')
    byq = collections.Counter()
    for r in runs: byq[r[0].rsplit(' ', 1)[0] if not r[0].startswith('(') else r[0]] += r[4]
    print('   CPU by quest (all runs):')
    for q, c in byq.most_common(15): print(f'     {q:<42} {c:6.1f} s  {c / cpu:5.1%}')
