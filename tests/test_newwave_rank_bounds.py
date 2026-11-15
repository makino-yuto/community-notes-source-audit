"""Independent exhaustive check of the exploratory policy's sharp bounds."""
import itertools
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from newwave_rank_sources import gain_bounds

class GainBoundsTest(unittest.TestCase):
    def test_bounds_match_all_binary_completions(self):
        for n in range(1,6):
            codes=[str(i) for i in range(n)]
            for states in itertools.product(('accessible','not_accessible','unresolved'),repeat=n):
                labels={c:{'outcome':y} for c,y in zip(codes,states)}
                unknown=[i for i,y in enumerate(states) if y=='unresolved']
                for selected in codes:
                    possible=[]
                    for completion in itertools.product((0,1),repeat=len(unknown)):
                        values=[int(y=='accessible') for y in states]
                        for i,v in zip(unknown,completion):values[i]=v
                        possible.append(values[int(selected)]-sum(values)/n)
                    lower,upper,point=gain_bounds(codes,selected,labels)
                    self.assertAlmostEqual(lower,min(possible))
                    self.assertAlmostEqual(upper,max(possible))
                    self.assertLessEqual(lower-1e-12,point)
                    self.assertLessEqual(point,upper+1e-12)

if __name__=='__main__':unittest.main()
