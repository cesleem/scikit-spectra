from copy import deepcopy, copy
import numpy as np
from pandas import DatetimeIndex, Timestamp

from pyuvvis.core.abcindex import ConversionIndex, _parse_unit
from pyuvvis.units.abcunits import UnitError
from pyuvvis.units.intvlunit import INTVLUNITS, TimeDelta, DateTime

class TimeIndex(ConversionIndex):
    """ Stores time labels as Timestamps, Time Deltas or cumulative intervals
    ie seconds, minutes, days from t=0.  Timestamps (e.g. datetimes) are 
    stored as objects, while seconds, minutes etc.. are stored as floats.  
    Therefore, some extra logic is in place to fix breaking points with the
    dtype would otherwise cause errors, mostly the case when dataframe does
    slicing or indexing.
    """
    unitdict = INTVLUNITS

    # Overload because datetime and interval need different array types
    # i.e. seconds --> float64 while dti ---> timestamp
    def __new__(cls, input_array, unit=None):
        """ Unit is valid key of unitdict """
        if unit:
            # dti, timedelta
            if unit == 'intvl' or unit == 'dti':
                dtype = 'object'
            else:
                dtype = 'float64'

            # IF INPUTARRAY COMES IN AS A PANDAS DATETIMEINDEX, FORMATS IT
            # TO AN ARRAY OF DATETIMES THEN TO AN ARRAY OF TIMESTAMPS,
            # THE ARRAY OF TIMESTAMPS IS NECESSARY FOR TIMEINDEX
            if isinstance(input_array, DatetimeIndex):
                #Convert datetimes to timestamp
                input_array = np.array(input_array.to_pydatetime())
                input_array = np.array([Timestamp(x) for x in input_array])

        obj = np.asarray(input_array, dtype=dtype).view(cls)   
        
        if unit == 'dti':
            obj._stored_dti = input_array
        else:
            obj._stored_dti = None

        # Ensure valid unit
        obj._unit = _parse_unit(unit, cls.unitdict)
        return obj   


    def convert(self, outunit):
        """Converts spectral units (see abcindex.convert()).  Handles special
        case of converting to datetimeindex, since the DateTime unit does
        not have conversions; instead the datetimeindex is stored in this
        TimeIndex class and needs to be handled separately.
        """

        # Handle non-dti conversion and conversions involvin DTI and None
        try:
            return super(TimeIndex, self).convert(outunit)
        except DatetimeCanonicalError:
            pass

        # DTI
        if outunit.short == 'dti' and inunit.short == 'dti':
            return self.__class__(self, unit = 'dti')


        
#        canonical = inunit.to_canonical(np.array(self))
#        arrayout = outunit.from_canonical(canonical)
#        return self.__class__(arrayout, unit=outunit.short)             
            

        #DTI TO SOMETHING ELSE
        elif outunit.short == 'dti' and inunit.short != 'dti':
            #RETURN DIRECTLY FROM STORED DTI
            return self.dti 

            
        #SOMETHING ELSE TO DTI            
        elif outunit.short != 'dti' and inunit.short == 'dti':
            #DTI TO CANONICAL
            #CANONICAL TO OUTUNIT
            NotImplemented

            
        # Should never happen
        else:
            raise IndexError("SOME LOGIC APPARENTLY NOT ACCOUNT FOR")
    



    @classmethod
    def from_datetime(cls, dti):
        """ Construct IntervalIndex from a pandas DatetimeIndex.

        Parameters
        ----------      
        dti: DateTimeIndex

        cumsum: bool (True)
            Interval will be returned as running sum.  Ie 0,3,6 for 3 second
            intervals.  If not, returns 3, 3, 3

        Returns
        -------
        TimeIndex

        Additional
        ----------
        This generates an IntervalIndex, but populates the DateTime unit with
        attributes directly from the datetimeindex, including start, stop, 
        periods, freq etc through the from_datetime method()"""

        if not isinstance(dti, DatetimeIndex):
            raise UnitError("Please pass a datetime index.")

#      datetimeunit = DateTime.from_datetime(dti)

        # Set DateTime unit to the one just created through from_datetime 
        intervalindex = cls(dti, unit='dti')
#        intervalindex.unitdict['dti'].datetimeindex = dti
        return intervalindex

    def __getslice__(self, start, stop) :
        """This solves a subtle bug, where __getitem__ is not called, and all
        the dimensional checking not done, when a slice of only the first
        dimension is taken, e.g. a[1:3]. From the Python docs:
           Deprecated since version 2.0: Support slice objects as parameters
           to the __getitem__() method. (However, built-in types in CPython
           currently still implement __getslice__(). Therefore, you have to
           override it in derived classes when implementing slicing.)
        """
        return self.__getitem__(slice(start, stop))

    def __getitem__(self, key):
        """ When slicing, the datetimeindex should also be sliced. Otherwise,
        when converting to datetimeindex, could have length mismatch.  EG:
        
        min = ts.convert('m')[0:5]
        len(min) = 5
        dti = min.convert('dti')
        len(dti) = <length of original array>
        """
        out = super(TimeIndex, self).__getitem__(key)
        # If not returning a single value (eg index[0])
        if hasattr(out, '__iter__'):
            if hasattr(out, '_stored_dti'):
                # unitdict will get copied by reference; need new 
                out._stored_dti = out._dtored_dti.__getitem__(key) #copy?
#                out.unitdict = deepcopy(self.unitdict)
#                out.unitdict['dti'].datetimeindex = deepcopy(out.unitdict['dti'].datetimeindex.__getitem__(key))
        return out

    @property
    def datetimeindex(self):
        return self.unitdict['dti'].datetimeindex


    # DOESNT WORK
    @property
    def cumsum(self):
        return self.unitdict['dti'].cumsum

    @cumsum.setter
    def cumsum(self, cumsum):
        if cumsum:
            cumsum = True
        else:
            cumsum = False
        self.unitdict['dti'].cumsum = cumsum


    @property
    def is_all_dates(self):
        """ Overwirte this Index method because it's source of many issues
        deep in cython level.  Basically, only should be called if python
        objects.  Otherwise, get ValueError:
             Buffer dtype mismatch, expected 'Python object' but got 'double'
        """
        if self.dtype != 'object':
            return False
        else:
            return super(ConversionIndex, self).is_all_dates    


    # Hack to return _engine type correctly for mixed index objects like TimeIndex
    @property
    def _engine_type(self):
        import pandas.index as _index      
        if self.dtype == 'object':
            return _index.ObjectEngine
        elif self.dtype == 'float64':
            return _index.Float64Engine
        else:
            raise IndexError("Not sure which Engine to return for dtype %s" % self.dtype)      


if __name__ == '__main__':
    from pandas import date_range

    idx = TimeIndex([1,2,3])
    idx = idx.convert('s')
    idx = idx.convert('m')

    #From datetime constructor
    idx = TimeIndex.from_datetime(date_range(start='3/3/12',periods=30,freq='45s'))
    print idx
    for unit in INTVLUNITS:
        print unit, idx.convert(unit)

    print idx.unitdict.keys()

#   idx.cumsum = False
#   for unit in INTVLUNITS:
#      print unit, idx.convert(unit)   