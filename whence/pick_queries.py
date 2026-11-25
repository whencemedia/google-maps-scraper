"""Pick today's batch of searches from lead-queries.txt, rotating through the list day by day."""
import datetime
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
count = int(sys.argv[1]) if len(sys.argv) > 1 else 8
out = sys.argv[2] if len(sys.argv) > 2 else "queries-today.txt"

with open(os.path.join(here, "lead-queries.txt"), encoding="utf-8") as f:
    queries = [q.strip() for q in f if q.strip() and not q.startswith("#")]

day = datetime.date.today().toordinal()
start = (day * count) % len(queries)
batch = [queries[(start + i) % len(queries)] for i in range(min(count, len(queries)))]

with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(batch) + "\n")
print("\n".join(batch))
