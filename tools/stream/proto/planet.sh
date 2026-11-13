#!/bin/bash
# The planet location store and the versions before 11-08's stream, then the six day diffs to 11-08T00Z.
cd /c/Users/kk/Code/sc-open-quests/.scratch/store || exit 1
python store.py build --pbf "C:/Users/kk/Code/.osm-data/planet/history-261102.osh.pbf" --store planet.loc --name planet || { echo "FAILED build"; exit 1; }
python store.py diffs --store planet.loc --priors priors-planet.pickle || { echo "FAILED diffs"; exit 1; }
echo "planet done"
