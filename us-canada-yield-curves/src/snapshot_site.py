"""Review captures of the standalone curve chart."""
from pathlib import Path
from staticsites.snapshots import Snapshotter

SNAPSHOT = Snapshotter(Path(__file__).resolve().parent.parent, kind='chart', expected_plots=2)

if __name__ == '__main__':
    SNAPSHOT.main()
