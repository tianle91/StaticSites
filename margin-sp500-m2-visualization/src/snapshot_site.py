"""Project snapshot configuration; capture is a build-time shared component."""
from pathlib import Path
from staticsites.snapshots import Snapshotter

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = Snapshotter(ROOT, kind='chart', expected_plots=1)

if __name__ == '__main__':
    SNAPSHOT.main()
