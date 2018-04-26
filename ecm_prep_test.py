#!/usr/bin/env python3

""" Tests for running the measure preparation routine """

# Import code to be tested
import ecm_prep
# Import needed packages
import unittest
import numpy
import os
from collections import OrderedDict
import warnings
import copy
import itertools


class CommonMethods(object):
    """Define common methods for use in all tests below."""

    def dict_check(self, dict1, dict2):
        """Check the equality of two dicts.

        Args:
            dict1 (dict): First dictionary to be compared
            dict2 (dict): Second dictionary to be compared

        Raises:
            AssertionError: If dictionaries are not equal.
        """
        # zip() and zip_longest() produce tuples for the items
        # identified, where in the case of a dict, the first item
        # in the tuple is the key and the second item is the value;
        # in the case where the dicts are not of identical size,
        # zip_longest() will use the fill value created below as a
        # substitute in the dict that has missing content; this
        # value is given as a tuple to be of comparable structure
        # to the normal output from zip_longest()
        fill_val = ('substituted entry', 5.2)

        # In this structure, k and k2 are the keys that correspond to
        # the dicts or unitary values that are found in i and i2,
        # respectively, at the current level of the recursive
        # exploration of dict1 and dict2, respectively
        for (k, i), (k2, i2) in itertools.zip_longest(sorted(dict1.items()),
                                                      sorted(dict2.items()),
                                                      fillvalue=fill_val):

            # Confirm that at the current location in the dict structure,
            # the keys are equal; this should fail if one of the dicts
            # is empty, is missing section(s), or has different key names
            self.assertEqual(k, k2)

            # If the recursion has not yet reached the terminal/leaf node
            if isinstance(i, dict):
                # Test that the dicts from the current keys are equal
                self.assertCountEqual(i, i2)
                # Continue to recursively traverse the dict
                self.dict_check(i, i2)
            # At the terminal/leaf node, formatted as a numpy array or list
            # (for time sensitive valuation test cases)
            elif isinstance(i, numpy.ndarray) or isinstance(i, list):
                self.assertTrue(type(i) == type(i2) and len(i) == len(i2))
                for x in range(0, len(i)):
                    self.assertAlmostEqual(i[x], i2[x], places=5)
            # At the terminal/leaf node, formatted as a point value
            else:
                # Compare the values, allowing for floating point inaccuracy
                self.assertAlmostEqual(i, i2, places=2)


class EPlusGlobalsTest(unittest.TestCase, CommonMethods):
    """Test 'find_vintage_weights' function.

    Ensure building vintage square footages are read in properly from a
    cbecs data file and that the proper weights are derived for mapping
    EnergyPlus building vintages to Scout's 'new' and 'retrofit' building
    structure types.

    Attributes:
        cbecs_sf_byvint (dict): Commercial square footage by vintage data.
        eplus_globals_ok (object): EPlusGlobals object with square footage and
            vintage weights attributes to test against expected outputs.
        eplus_failpath (string): Path to invalid EnergyPlus simulation data
            file that should cause EPlusGlobals object instantiation to fail.
        ok_out_weights (dict): Correct vintage weights output for
            'find_vintage_weights'function given valid inputs.
    """

    @classmethod
    def setUpClass(cls):
        """Define variables for use across all class functions."""
        base_dir = os.getcwd()
        cls.cbecs_sf_byvint = {
            '2004 to 2007': 6524.0, '1960 to 1969': 10362.0,
            '1946 to 1959': 7381.0, '1970 to 1979': 10846.0,
            '1990 to 1999': 13803.0, '2000 to 2003': 7215.0,
            'Before 1920': 3980.0, '2008 to 2012': 5726.0,
            '1920 to 1945': 6020.0, '1980 to 1989': 15185.0}
        cls.eplus_globals_ok = ecm_prep.EPlusGlobals(
            base_dir + "/ecm_definitions/energyplus_data/energyplus_test_ok",
            cls.cbecs_sf_byvint)
        cls.eplus_failpath = \
            base_dir + "/ecm_definitions/energyplus_data/energyplus_test_fail"
        cls.ok_out_weights = {
            'DOE Ref 1980-2004': 0.42, '90.1-2004': 0.07,
            '90.1-2010': 0.07, 'DOE Ref Pre-1980': 0.44,
            '90.1-2013': 1}

    def test_vintageweights(self):
        """Test find_vintage_weights function given valid inputs.

        Note:
            Ensure EnergyPlus building vintage type data are correctly weighted
            by their square footages (derived from CBECs data).

        Raises:
            AssertionError: If function yields unexpected results.
        """
        self.dict_check(
            self.eplus_globals_ok.find_vintage_weights(),
            self.ok_out_weights)

    # Test that an error is raised when unexpected eplus vintages are present
    def test_vintageweights_fail(self):
        """Test find_vintage_weights function given invalid inputs.

        Note:
            Ensure that KeyError is raised when an unexpected EnergyPlus
            building vintage is present.

        Raises:
            AssertionError: If KeyError is not raised.
        """
        with self.assertRaises(KeyError):
            ecm_prep.EPlusGlobals(
                self.eplus_failpath,
                self.cbecs_sf_byvint).find_vintage_weights()


class EPlusUpdateTest(unittest.TestCase, CommonMethods):
    """Test the 'fill_eplus' function and its supporting functions.

    Ensure that the 'build_array' function properly assembles a set of input
    CSVs into a structured array and that the 'create_perf_dict' and
    'fill_perf_dict' functions properly initialize and fill a measure
    performance dictionary with results from an EnergyPlus simulation output
    file.

    Attributes:
        meas (object): Measure object instantiated based on sample_measure_in
            attributes.
        eplus_dir (string): EnergyPlus simulation output file directory.
        eplus_coltypes (list): List of expected EnergyPlus output data types.
        eplus_basecols (list): Variable columns that should never be removed.
        mseg_in (dict): Sample baseline microsegment stock/energy data.
        ok_eplus_vintagewts (dict): Sample EnergyPlus vintage weights.
        ok_eplusfiles_in (list): List of all EnergyPlus simulation file names.
        ok_perfarray_in (numpy recarray): Valid structured array of
            EnergyPlus-based relative savings data.
        fail_perfarray_in (numpy recarray): Invalid structured array of
            EnergyPlus-based relative savings data (missing certain climate
            zones, building types, and building vintages).
        fail_perfdictempty_in (dict): Invalid empty dictionary to fill with
            EnergyPlus-based performance information broken down by climate
            zone, building type/vintage, fuel type, and end use (dictionary
            includes invalid climate zone key).
        ok_array_type_out (string): The array type that should be yielded by
            'convert_to_array' given valid input.
        ok_array_length_out (int): The array length that should be yielded by
            'convert_to_array' given valid input.
        ok_array_names_out (tuple): Tuple of column names for the recarray that
            should be yielded by 'convert_to_array' given valid input.
        ok_perfdictempty_out (dict): The empty dictionary that should be
            yielded by 'create_perf_dict' given valid inputs.
        ok_perfdictfill_out (dict): The dictionary filled with EnergyPlus-based
            measure performance information that should be yielded by
            'fill_perf_dict' and 'fill_eplus' given valid inputs.

    Raises:
        AssertionError: If function yields unexpected results or does not
            raise a KeyError when it should.
    """

    @classmethod
    def setUpClass(cls):
        """Define variables and objects for use across all class functions."""
        # Sample measure attributes to use in instantiating Measure object.
        sample_measure_in = OrderedDict([
            ("name", "eplus sample measure 1"),
            ("status", OrderedDict([
                ("active", 1), ("updated", 1)])),
            ("installed_cost", 25),
            ("cost_units", "2014$/unit"),
            ("energy_efficiency", OrderedDict([
                ("EnergyPlus file", "eplus_sample_measure")])),
            ("energy_efficiency_units", OrderedDict([
                ("primary", "relative savings (constant)"),
                ("secondary", "relative savings (constant)")])),
            ("energy_efficiency_source", None),
            ("market_entry_year", None),
            ("market_exit_year", None),
            ("product_lifetime", 10),
            ("structure_type", ["new", "retrofit"]),
            ("bldg_type", ["assembly", "education"]),
            ("climate_zone", ["hot dry", "mixed humid"]),
            ("fuel_type", OrderedDict([
                ("primary", ["electricity"]),
                ("secondary", [
                    "electricity", "natural gas", "distillate"])])),
            ("fuel_switch_to", None),
            ("end_use", OrderedDict([
                ("primary", ["lighting"]),
                ("secondary", ["heating", "cooling"])])),
            ("technology", OrderedDict([
                ("primary", [
                    "technology A", "technology B", "technology C"]),
                ("secondary", ["windows conduction", "windows solar"])]))])
        # Base directory
        base_dir = os.getcwd()
        # Useful global variables for the sample measure object
        handyvars = ecm_prep.UsefulVars(base_dir,
                                        ecm_prep.UsefulInputFiles())
        cls.meas = ecm_prep.Measure(handyvars, **sample_measure_in)
        # Finalize the measure's 'technology_type' attribute (handled by the
        # 'fill_attr' function, which is not run as part of this test)
        cls.meas.technology_type = {"primary": "supply", "secondary": "demand"}
        cls.eplus_dir = \
            base_dir + "/ecm_definitions/energyplus_data/energyplus_test_ok"
        cls.eplus_coltypes = [
            ('building_type', '<U50'), ('climate_zone', '<U50'),
            ('template', '<U50'), ('measure', '<U50'), ('status', '<U50'),
            ('ep_version', '<U50'), ('os_version', '<U50'),
            ('timestamp', '<U50'), ('cooling_electricity', '<f8'),
            ('cooling_water', '<f8'), ('district_chilled_water', '<f8'),
            ('district_hot_water_heating', '<f8'),
            ('district_hot_water_service_hot_water', '<f8'),
            ('exterior_equipment_electricity', '<f8'),
            ('exterior_equipment_gas', '<f8'),
            ('exterior_equipment_other_fuel', '<f8'),
            ('exterior_equipment_water', '<f8'),
            ('exterior_lighting_electricity', '<f8'),
            ('fan_electricity', '<f8'),
            ('floor_area', '<f8'), ('generated_electricity', '<f8'),
            ('heat_recovery_electricity', '<f8'),
            ('heat_rejection_electricity', '<f8'),
            ('heating_electricity', '<f8'), ('heating_gas', '<f8'),
            ('heating_other_fuel', '<f8'), ('heating_water', '<f8'),
            ('humidification_electricity', '<f8'),
            ('humidification_water', '<f8'),
            ('interior_equipment_electricity', '<f8'),
            ('interior_equipment_gas', '<f8'),
            ('interior_equipment_other_fuel', '<f8'),
            ('interior_equipment_water', '<f8'),
            ('interior_lighting_electricity', '<f8'),
            ('net_site_electricity', '<f8'), ('net_water', '<f8'),
            ('pump_electricity', '<f8'),
            ('refrigeration_electricity', '<f8'),
            ('service_water', '<f8'),
            ('service_water_heating_electricity', '<f8'),
            ('service_water_heating_gas', '<f8'),
            ('service_water_heating_other_fuel', '<f8'), ('total_gas', '<f8'),
            ('total_other_fuel', '<f8'), ('total_site_electricity', '<f8'),
            ('total_water', '<f8')]
        cls.eplus_basecols = [
            'building_type', 'climate_zone', 'template', 'measure']
        cls.mseg_in = {
            'hot dry': {
                'education': {
                    'electricity': {
                        'lighting': {
                            "technology A": 0,
                            "technology B": 0,
                            "technology C": 0},
                        'heating': {
                            'supply': {
                                'technology A': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}},
                        'cooling': {
                            'supply': {
                                'technology A': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}}},
                    'natural gas': {
                        'heating': {
                            'supply': {
                                'technology A': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}},
                        'cooling': {
                            'supply': {
                                'technology A': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}}},
                    'distillate': {
                        'heating': {
                            'supply': {
                                'technology A': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}}}},
                'assembly': {
                    'electricity': {
                        'lighting': {
                            "technology A": 0,
                            "technology B": 0,
                            "technology C": 0},
                        'heating': {
                            'supply': {
                                'technology A': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}},
                        'cooling': {
                            'supply': {
                                'technology A': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}}},
                    'natural gas': {
                        'heating': {
                            'supply': {
                                'technology A': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}},
                        'cooling': {
                            'supply': {
                                'technology A': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}}},
                    'distillate': {
                        'heating': {
                            'supply': {
                                'technology A': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}}}}},
            'mixed humid': {
                'education': {
                    'electricity': {
                        'lighting': {
                            "technology A": 0,
                            "technology B": 0,
                            "technology C": 0},
                        'heating': {
                            'supply': {
                                'technology A': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}},
                        'cooling': {
                            'supply': {
                                'technology A': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}}},
                    'natural gas': {
                        'heating': {
                            'supply': {
                                'technology A': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}},
                        'cooling': {
                            'supply': {
                                'technology A': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}}},
                    'distillate': {
                        'heating': {
                            'supply': {
                                'technology A': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}}}},
                'assembly': {
                    'electricity': {
                        'lighting': {
                            "technology A": 0,
                            "technology B": 0,
                            "technology C": 0},
                        'heating': {
                            'supply': {
                                'technology A': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}},
                        'cooling': {
                            'supply': {
                                'ASHP': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}}},
                    'natural gas': {
                        'heating': {
                            'supply': {
                                'technology A': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}},
                        'cooling': {
                            'supply': {
                                'technology A': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}}},
                    'distillate': {
                        'heating': {
                            'supply': {
                                'technology A': 0},
                            'demand': {
                                'windows conduction': 0,
                                'windows solar': 0}}}}}}
        # Set EnergyPlus building vintage weights (based on square footage)
        cls.ok_eplus_vintagewts = {
            'DOE Ref Pre-1980': 0.44, '90.1-2004': 0.07, '90.1-2010': 0.07,
            '90.1-2013': 1, 'DOE Ref 1980-2004': 0.42}
        cls.ok_eplusfiles_in = [
            "fullservicerestaurant_scout_2016-07-23-16-25-59.csv",
            "secondaryschool_scout_2016-07-23-16-25-59.csv",
            "primaryschool_scout_2016-07-23-16-25-59.csv",
            "smallhotel_scout_2016-07-23-16-25-59.csv",
            "hospital_scout_2016-07-23-16-25-59.csv"]
        # Set full paths for EnergyPlus files that are relevant to the measure
        eplusfiles_in_fullpaths = [cls.eplus_dir + '/' + x for x in [
            "secondaryschool_scout_2016-07-23-16-25-59.csv",
            "primaryschool_scout_2016-07-23-16-25-59.csv",
            "hospital_scout_2016-07-23-16-25-59.csv"]]
        # Use 'build_array' to generate test input data for 'fill_eplus'
        cls.ok_perfarray_in = cls.meas.build_array(
            cls.eplus_coltypes, eplusfiles_in_fullpaths)
        cls.fail_perfarray_in = numpy.rec.array([
            ('BA-MixedHumid', 'SecondarySchool', '90.1-2013', 'Success',
             0, 0.5, 0.5, 0.25, 0.25, 0, 0.25, 0.75, 0, -0.1, 0.1, 0.5, -0.2),
            ('BA-HotDry', 'PrimarySchool', 'DOE Ref 1980-2004', 'Success',
             0, 0.5, 0.5, 0.25, 0.25, 0, 0.25, 0.75, 0, -0.1, 0.1, 0.5, -0.2)],
            dtype=[('climate_zone', '<U13'), ('building_type', '<U22'),
                   ('template', '<U17'), ('status', 'U7'),
                   ('floor_area', '<f8'),
                   ('total_site_electricity', '<f8'),
                   ('net_site_electricity', '<f8'),
                   ('total_gas', '<f8'), ('total_other_fuel', '<f8'),
                   ('total_water', '<f8'), ('net_water', '<f8'),
                   ('interior_lighting_electricity', '<f8'),
                   ('interior_equipment_electricity', '<f8'),
                   ('heating_electricity', '<f8'),
                   ('cooling_electricity', '<f8'),
                   ('heating_gas', '<f8'),
                   ('heat_recovery_electricity', '<f8')])
        cls.fail_perfdictempty_in = {
            "primary": {
                'blazing hot': {
                    'education': {
                        'electricity': {
                            'lighting': {'retrofit': 0, 'new': 0}}},
                    'assembly': {
                        'electricity': {
                            'lighting': {'retrofit': 0, 'new': 0}}}},
                'mixed humid': {
                    'education': {
                        'electricity': {
                            'lighting': {'retrofit': 0, 'new': 0}}},
                    'assembly': {
                        'electricity': {
                            'lighting': {'retrofit': 0, 'new': 0}}}}},
            "secondary": {
                'blazing hot': {
                    'education': {
                        'electricity': {
                            'heating': {'retrofit': 0, 'new': 0},
                            'cooling': {'retrofit': 0, 'new': 0}},
                        'natural gas': {
                            'heating': {'retrofit': 0, 'new': 0}}},
                    'assembly': {
                        'electricity': {
                            'heating': {'retrofit': 0, 'new': 0},
                            'cooling': {'retrofit': 0, 'new': 0}},
                        'natural gas': {
                            'heating': {'retrofit': 0, 'new': 0}}}},
                'mixed humid': {
                    'education': {
                        'electricity': {
                            'heating': {'retrofit': 0, 'new': 0},
                            'cooling': {'retrofit': 0, 'new': 0}},
                        'natural gas': {
                            'heating': {'retrofit': 0, 'new': 0}}},
                    'assembly': {
                        'electricity': {
                            'heating': {'retrofit': 0, 'new': 0},
                            'cooling': {'retrofit': 0, 'new': 0}},
                        'natural gas': {
                            'heating': {'retrofit': 0, 'new': 0}}}}}}
        cls.ok_array_length_out = 240
        cls.ok_arraynames_out = cls.ok_perfarray_in.dtype.names
        cls.ok_perfdictempty_out = {
            "primary": {
                'hot dry': {
                    'education': {
                        'electricity': {
                            'lighting': {'retrofit': 0, 'new': 0}}},
                    'assembly': {
                        'electricity': {
                            'lighting': {'retrofit': 0, 'new': 0}}}},
                'mixed humid': {
                    'education': {
                        'electricity': {
                            'lighting': {'retrofit': 0, 'new': 0}}},
                    'assembly': {
                        'electricity': {
                            'lighting': {'retrofit': 0, 'new': 0}}}}},
            "secondary": {
                'hot dry': {
                    'education': {
                        'electricity': {
                            'heating': {'retrofit': 0, 'new': 0},
                            'cooling': {'retrofit': 0, 'new': 0}},
                        'natural gas': {
                            'heating': {'retrofit': 0, 'new': 0}},
                        'distillate': {
                            'heating': {'retrofit': 0, 'new': 0}}},
                    'assembly': {
                        'electricity': {
                            'heating': {'retrofit': 0, 'new': 0},
                            'cooling': {'retrofit': 0, 'new': 0}},
                        'natural gas': {
                            'heating': {'retrofit': 0, 'new': 0}},
                        'distillate': {
                            'heating': {'retrofit': 0, 'new': 0}}}},
                'mixed humid': {
                    'education': {
                        'electricity': {
                            'heating': {'retrofit': 0, 'new': 0},
                            'cooling': {'retrofit': 0, 'new': 0}},
                        'natural gas': {
                            'heating': {'retrofit': 0, 'new': 0}},
                        'distillate': {
                            'heating': {'retrofit': 0, 'new': 0}}},
                    'assembly': {
                        'electricity': {
                            'heating': {'retrofit': 0, 'new': 0},
                            'cooling': {'retrofit': 0, 'new': 0}},
                        'natural gas': {
                            'heating': {'retrofit': 0, 'new': 0}},
                        'distillate': {
                            'heating': {'retrofit': 0, 'new': 0}}}}}}
        cls.ok_perfdictfill_out = {
            "primary": {
                'hot dry': {
                    'education': {
                        'electricity': {
                            'lighting': {'retrofit': 0.5, 'new': 0.5}}},
                    'assembly': {
                        'electricity': {
                            'lighting': {'retrofit': 0.5, 'new': 0.5}}}},
                'mixed humid': {
                    'education': {
                        'electricity': {
                            'lighting': {
                                'retrofit': 0.75, 'new': 0.935}}},
                    'assembly': {
                        'electricity': {
                            'lighting': {
                                'retrofit': 0.75, 'new': 1}}}}},
            "secondary": {
                'hot dry': {
                    'education': {
                        'electricity': {
                            'heating': {'retrofit': 0, 'new': 0},
                            'cooling': {'retrofit': 0.75, 'new': 0.555}},
                        'natural gas': {
                            'heating': {
                                'retrofit': 1.25, 'new': 1.25}},
                        'distillate': {
                            'heating': {'retrofit': 0, 'new': 0}}},
                    'assembly': {
                        'electricity': {
                            'heating': {'retrofit': 0, 'new': 0},
                            'cooling': {'retrofit': 0.75, 'new': 0.75}},
                        'natural gas': {
                            'heating': {
                                'retrofit': 1.25, 'new': 1.25}},
                        'distillate': {
                            'heating': {'retrofit': 0, 'new': 0}}}},
                'mixed humid': {
                    'education': {
                        'electricity': {
                            'heating': {'retrofit': 0, 'new': 0},
                            'cooling': {'retrofit': 0.5, 'new': 0.87}},
                        'natural gas': {
                            'heating': {
                                'retrofit': 1.5, 'new': 1.13}},
                        'distillate': {
                            'heating': {'retrofit': 0, 'new': 0}}},
                    'assembly': {
                        'electricity': {
                            'heating': {'retrofit': 0, 'new': 0},
                            'cooling': {'retrofit': 0.5, 'new': 1}},
                        'natural gas': {
                            'heating': {
                                'retrofit': 1.5, 'new': 1}},
                        'distillate': {
                            'heating': {'retrofit': 0, 'new': 0}}}}}}

    def test_array_build(self):
        """Test 'build_array' function given valid inputs.

        Note:
            Ensure correct assembly of numpy arrays from all EnergyPlus
            files that are relevant to a test measure.

        Raises:
            AssertionError: If function yields unexpected results.
        """
        # Check for correct column names and length of the converted array
        self.assertEqual(
            [self.ok_perfarray_in.dtype.names, len(self.ok_perfarray_in)],
            [self.ok_arraynames_out, self.ok_array_length_out])

    def test_dict_creation(self):
        """Test 'create_perf_dict' function given valid inputs.

        Note:
            Ensure correct generation of measure performance dictionary.

        Raises:
            AssertionError: If function yields unexpected results.
        """
        self.dict_check(self.meas.create_perf_dict(
            self.mseg_in), self.ok_perfdictempty_out)

    def test_dict_fill(self):
        """Test 'fill_perf_dict' function given valid inputs.

        Note:
            Ensure correct updating of measure performance dictionary
            with EnergyPlus simulation results.

        Raises:
            AssertionError: If function yields unexpected results.
        """
        self.dict_check(
            self.meas.fill_perf_dict(
                self.ok_perfdictempty_out, self.ok_perfarray_in,
                self.ok_eplus_vintagewts, self.eplus_basecols,
                eplus_bldg_types={}),
            self.ok_perfdictfill_out)

    def test_dict_fill_fail(self):
        """Test 'fill_perf_dict' function given invalid inputs.

        Note:
            Ensure function fails when given either invalid blank
            performance dictionary to fill or invalid input array of
            EnergyPlus simulation information to fill the dict with.

        Raises:
            AssertionError: If KeyError is not raised
        """
        with self.assertRaises(KeyError):
            # Case with invalid input dictionary
            self.meas.fill_perf_dict(
                self.fail_perfdictempty_in, self.ok_perfarray_in,
                self.ok_eplus_vintagewts, self.eplus_basecols,
                eplus_bldg_types={})
            # Case with incomplete input array of EnergyPlus information
            self.meas.fill_perf_dict(
                self.ok_perfdictempty_out, self.fail_perfarray_in,
                self.ok_eplus_vintagewts, self.eplus_basecols,
                eplus_bldg_types={})

    def test_fill_eplus(self):
        """Test 'fill_eplus' function given valid inputs.

        Note:
            Ensure proper updating of measure performance with
            EnergyPlus simulation results from start ('convert_to_array')
            to finish ('fill_perf_dict').

        Raises:
            AssertionError: If function yields unexpected results.
        """
        self.meas.fill_eplus(
            self.mseg_in, self.eplus_dir, self.eplus_coltypes,
            self.ok_eplusfiles_in, self.ok_eplus_vintagewts,
            self.eplus_basecols)
        # Check for properly updated measure energy_efficiency,
        # energy_efficiency_source, and energy_efficiency_source_quality
        # attributes.
        self.dict_check(
            self.meas.energy_efficiency, self.ok_perfdictfill_out)
        self.assertEqual(
            self.meas.energy_efficiency_source, 'EnergyPlus/OpenStudio')


class MarketUpdatesTest(unittest.TestCase, CommonMethods):
    """Test 'fill_mkts' function.

    Ensure that the function properly fills in market microsegment data
    for a series of sample measures.

    Attributes:
        verbose (NoneType): Determines whether to print all user messages.
        convert_data (dict): ECM cost conversion data.
        tsv_data (dict): Data needed for time-sensitive efficiency valuation.
        sample_mseg_in (dict): Sample baseline microsegment stock/energy.
        sample_cpl_in (dict): Sample baseline technology cost, performance,
            and lifetime.
        ok_tpmeas_fullchk_in (list): Valid sample measure information
            to update with markets data; measure cost, performance, and life
            attributes are given as point estimates. Used to check the full
            measure 'markets' attribute under a 'Technical potential scenario.
        ok_tpmeas_partchk_in (list): Valid sample measure information to update
            with markets data; measure cost, performance, and lifetime
            attributes are given as point estimates. Used to check the
            'master_mseg' branch of measure 'markets' attribute under a
            'Technical potential scenario.
        ok_mapmeas_partchk_in (list): Valid sample measure information
            to update with markets data; measure cost, performance, and life
            attributes are given as point estimates. Used to check the
            'master_mseg' branch of measure 'markets' attribute under a 'Max
            adoption potential scenario.
        ok_distmeas_in (list): Valid sample measure information to
            update with markets data; measure cost, performance, and lifetime
            attributes are given as probability distributions.
        ok_partialmeas_in (list): Partially valid measure information to update
            with markets data.
        failmeas_in (list): Invalid sample measure information that should
            yield error when entered into function.
        warnmeas_in (list): Incomplete sample measure information that
            should yield warnings when entered into function (measure
            sub-market scaling fraction source attributions are invalid).
        ok_tpmeas_fullchk_msegout (list): Master market microsegments
            information that should be yielded given 'ok_tpmeas_fullchk_in'.
        ok_tpmeas_fullchk_competechoiceout (list): Consumer choice information
            that should be yielded given 'ok_tpmeas_fullchk_in'.
        ok_tpmeas_fullchk_msegadjout (list): Secondary microsegment adjustment
            information that should be yielded given 'ok_tpmeas_fullchk_in'.
        ok_tpmeas_fullchk_break_out (list): Output breakout information that
            should be yielded given 'ok_tpmeas_fullchk_in'.
        ok_tpmeas_partchk_msegout (list): Master market microsegments
            information that should be yielded given 'ok_tpmeas_partchk_in'.
        ok_mapmas_partchck_msegout (list): Master market microsegments
            information that should be yielded given 'ok_mapmeas_partchk_in'.
        ok_distmeas_out (list): Means and sampling Ns for measure energy/cost
            markets and lifetime that should be yielded given 'ok_distmeas_in'.
        ok_partialmeas_out (list): Master market microsegments information
            that should be yielded given 'ok_partialmeas_in'.
        ok_warnmeas_out (list): Warning messages that should be yielded
            given 'warnmeas_in'.
    """

    @classmethod
    def setUpClass(cls):
        """Define variables and objects for use across all class functions."""
        # Base directory
        base_dir = os.getcwd()
        handyvars = ecm_prep.UsefulVars(base_dir,
                                        ecm_prep.UsefulInputFiles())
        # Hard code aeo_years to fit test years
        handyvars.aeo_years = ["2009", "2010"]
        handyvars.retro_rate = 0.02
        # Hard code carbon intensity, site-source conversion, and cost data for
        # tests such that these data are not dependent on an input file that
        # may change in the future
        handyvars.ss_conv = {
            "electricity": {"2009": 3.19, "2010": 3.20},
            "natural gas": {"2009": 1.01, "2010": 1.01},
            "distillate": {"2009": 1.01, "2010": 1.01},
            "other fuel": {"2009": 1.01, "2010": 1.01}}
        handyvars.carb_int = {
            "residential": {
                "electricity": {"2009": 56.84702689, "2010": 56.16823191},
                "natural gas": {"2009": 56.51576602, "2010": 54.91762852},
                "distillate": {"2009": 49.5454521, "2010": 52.59751597},
                "other fuel": {"2009": 49.5454521, "2010": 52.59751597}},
            "commercial": {
                "electricity": {"2009": 56.84702689, "2010": 56.16823191},
                "natural gas": {"2009": 56.51576602, "2010": 54.91762852},
                "distillate": {"2009": 49.5454521, "2010": 52.59751597},
                "other fuel": {"2009": 49.5454521, "2010": 52.59751597}}}
        handyvars.ecosts = {
            "residential": {
                "electricity": {"2009": 10.14, "2010": 9.67},
                "natural gas": {"2009": 11.28, "2010": 10.78},
                "distillate": {"2009": 21.23, "2010": 20.59},
                "other fuel": {"2009": 21.23, "2010": 20.59}},
            "commercial": {
                "electricity": {"2009": 9.08, "2010": 8.55},
                "natural gas": {"2009": 8.96, "2010": 8.59},
                "distillate": {"2009": 14.81, "2010": 14.87},
                "other fuel": {"2009": 14.81, "2010": 14.87}}}
        handyvars.ccosts = {"2009": 33, "2010": 33}
        cls.verbose = None
        cls.convert_data = {}
        cls.tsv_data = {}
        cls.sample_mseg_in = {
            "AIA_CZ1": {
                "assembly": {
                    "total square footage": {"2009": 11, "2010": 11},
                    "new square footage": {"2009": 0, "2010": 0},
                    "electricity": {
                        "heating": {
                            "demand": {
                                "windows conduction": {
                                    "stock": "NA",
                                    "energy": {
                                        "2009": 0, "2010": 0}},
                                "windows solar": {
                                    "stock": "NA",
                                    "energy": {
                                        "2009": 1, "2010": 1}},
                                "lighting gain": {
                                    "stock": "NA",
                                    "energy": {
                                        "2009": -7, "2010": -7}}}},
                        "cooling": {
                            "demand": {
                                "windows conduction": {
                                    "stock": "NA",
                                    "energy": {
                                        "2009": 5, "2010": 5}},
                                "windows solar": {
                                    "stock": "NA",
                                    "energy": {
                                        "2009": 6, "2010": 6}},
                                "lighting gain": {
                                    "stock": "NA",
                                    "energy": {
                                        "2009": 6, "2010": 6}}}},
                        "lighting": {
                            "T5 F28": {
                                "stock": "NA",
                                "energy": {
                                    "2009": 11, "2010": 11}}},
                        "PCs": {
                            "stock": "NA",
                            "energy": {"2009": 12, "2010": 12}},
                        "MELs": {
                            "distribution transformers": {
                                "stock": "NA",
                                "energy": {"2009": 24, "2010": 24}
                            }
                        }}},
                "single family home": {
                    "total square footage": {"2009": 100, "2010": 200},
                    "total homes": {"2009": 1000, "2010": 1000},
                    "new homes": {"2009": 100, "2010": 50},
                    "electricity": {
                        "heating": {
                            "demand": {
                                "windows conduction": {
                                    "stock": "NA",
                                    "energy": {"2009": 0, "2010": 0}},
                                "windows solar": {
                                    "stock": "NA",
                                    "energy": {"2009": 1, "2010": 1}},
                                "infiltration": {
                                    "stock": "NA",
                                    "energy": {"2009": 10, "2010": 10}}},
                            "supply": {
                                "resistance heat": {
                                    "stock": {"2009": 2, "2010": 2},
                                    "energy": {"2009": 2, "2010": 2}},
                                "ASHP": {
                                    "stock": {"2009": 3, "2010": 3},
                                    "energy": {"2009": 3, "2010": 3}},
                                "GSHP": {
                                    "stock": {"2009": 4, "2010": 4},
                                    "energy": {"2009": 4, "2010": 4}}}},
                        "secondary heating": {
                            "demand": {
                                "windows conduction": {
                                    "stock": "NA",
                                    "energy": {"2009": 5, "2010": 5}},
                                "windows solar": {
                                    "stock": "NA",
                                    "energy": {"2009": 6, "2010": 6}},
                                "infiltration": {
                                    "stock": "NA",
                                    "energy": {"2009": 10, "2010": 10}}},
                            "supply": {"non-specific": 7}},
                        "cooling": {
                            "demand": {
                                "windows conduction": {
                                    "stock": "NA",
                                    "energy": {"2009": 5, "2010": 5}},
                                "windows solar": {
                                    "stock": "NA",
                                    "energy": {"2009": 6, "2010": 6}},
                                "infiltration": {
                                    "stock": "NA",
                                    "energy": {"2009": 10, "2010": 10}}},
                            "supply": {
                                "central AC": {
                                    "stock": {"2009": 7, "2010": 7},
                                    "energy": {"2009": 7, "2010": 7}},
                                "room AC": {
                                    "stock": {"2009": 8, "2010": 8},
                                    "energy": {"2009": 8, "2010": 8}},
                                "ASHP": {
                                    "stock": {"2009": 9, "2010": 9},
                                    "energy": {"2009": 9, "2010": 9}},
                                "GSHP": {
                                    "stock": {"2009": 10, "2010": 10},
                                    "energy": {"2009": 10, "2010": 10}}}},
                        "lighting": {
                            "linear fluorescent (LED)": {
                                "stock": {"2009": 11, "2010": 11},
                                "energy": {"2009": 11, "2010": 11}},
                            "general service (LED)": {
                                "stock": {"2009": 12, "2010": 12},
                                "energy": {"2009": 12, "2010": 12}},
                            "reflector (LED)": {
                                "stock": {"2009": 13, "2010": 13},
                                "energy": {"2009": 13, "2010": 13}},
                            "external (LED)": {
                                "stock": {"2009": 14, "2010": 14},
                                "energy": {"2009": 14, "2010": 14}}},
                        "refrigeration": {
                            "stock": {"2009": 111, "2010": 111},
                            "energy": {"2009": 111, "2010": 111}},
                        "TVs": {
                            "TVs": {
                                "stock": {"2009": 99, "2010": 99},
                                "energy": {"2009": 9, "2010": 9}},
                            "set top box": {
                                "stock": {"2009": 99, "2010": 99},
                                "energy": {"2009": 999, "2010": 999}}
                            },
                        "computers": {
                            "desktop PC": {
                                "stock": {"2009": 44, "2010": 44},
                                "energy": {"2009": 4, "2010": 4}},
                            "laptop PC": {
                                "stock": {"2009": 55, "2010": 55},
                                "energy": {"2009": 5, "2010": 5}}
                            },
                        "other (grid electric)": {
                            "freezers": {
                                "stock": {"2009": 222, "2010": 222},
                                "energy": {"2009": 222, "2010": 222}},
                            "other MELs": {
                                "stock": {"2009": 333, "2010": 333},
                                "energy": {"2009": 333, "2010": 333}}}},
                    "natural gas": {
                        "water heating": {
                            "stock": {"2009": 15, "2010": 15},
                            "energy": {"2009": 15, "2010": 15}},
                        "heating": {
                            "demand": {
                                "windows conduction": {
                                    "stock": "NA",
                                    "energy": {"2009": 0,
                                               "2010": 0}},
                                "windows solar": {
                                    "stock": "NA",
                                    "energy": {"2009": 1,
                                               "2010": 1}},
                                "infiltration": {
                                    "stock": "NA",
                                    "energy": {
                                        "2009": 10, "2010": 10}}}},
                        "secondary heating": {
                            "demand": {
                                "windows conduction": {
                                    "stock": "NA",
                                    "energy": {"2009": 5,
                                               "2010": 5}},
                                "windows solar": {
                                    "stock": "NA",
                                    "energy": {"2009": 6,
                                               "2010": 6}},
                                "infiltration": {
                                    "stock": "NA",
                                    "energy": {
                                        "2009": 10, "2010": 10}}}},
                        "cooling": {
                            "demand": {
                                "windows conduction": {
                                    "stock": "NA",
                                    "energy": {"2009": 5, "2010": 5}},
                                "windows solar": {
                                    "stock": "NA",
                                    "energy": {"2009": 6, "2010": 6}},
                                "infiltration": {
                                    "stock": "NA",
                                    "energy": {
                                        "2009": 10, "2010": 10}}}}}},
                "multi family home": {
                    "total square footage": {"2009": 300, "2010": 400},
                    "total homes": {"2009": 1000, "2010": 1000},
                    "new homes": {"2009": 100, "2010": 50},
                    "electricity": {
                        "heating": {
                            "demand": {
                                "windows conduction": {
                                    "stock": "NA",
                                    "energy": {"2009": 0, "2010": 0}},
                                "windows solar": {
                                    "stock": "NA",
                                    "energy": {"2009": 1, "2010": 1}}},
                            "supply": {
                                "resistance heat": {
                                    "stock": {"2009": 2, "2010": 2},
                                    "energy": {"2009": 2, "2010": 2}},
                                "ASHP": {
                                    "stock": {"2009": 3, "2010": 3},
                                    "energy": {"2009": 3, "2010": 3}},
                                "GSHP": {
                                    "stock": {"2009": 4, "2010": 4},
                                    "energy": {"2009": 4, "2010": 4}}}},
                        "lighting": {
                            "linear fluorescent (LED)": {
                                "stock": {"2009": 11, "2010": 11},
                                "energy": {"2009": 11, "2010": 11}},
                            "general service (LED)": {
                                "stock": {"2009": 12, "2010": 12},
                                "energy": {"2009": 12, "2010": 12}},
                            "reflector (LED)": {
                                "stock": {"2009": 13, "2010": 13},
                                "energy": {"2009": 13, "2010": 13}},
                            "external (LED)": {
                                "stock": {"2009": 14, "2010": 14},
                                "energy": {"2009": 14, "2010": 14}}}}}},
            "AIA_CZ2": {
                "single family home": {
                    "total square footage": {"2009": 500, "2010": 600},
                    "total homes": {"2009": 1000, "2010": 1000},
                    "new homes": {"2009": 100, "2010": 50},
                    "electricity": {
                        "heating": {
                            "demand": {
                                "windows conduction": {
                                    "stock": "NA",
                                    "energy": {"2009": 0, "2010": 0}},
                                "windows solar": {
                                    "stock": "NA",
                                    "energy": {"2009": 1, "2010": 1}},
                                "infiltration": {
                                    "stock": "NA",
                                    "energy": {"2009": 10, "2010": 10}}},
                            "supply": {
                                "resistance heat": {
                                    "stock": {"2009": 2, "2010": 2},
                                    "energy": {"2009": 2, "2010": 2}},
                                "ASHP": {
                                    "stock": {"2009": 3, "2010": 3},
                                    "energy": {"2009": 3, "2010": 3}},
                                "GSHP": {
                                    "stock": {"2009": 4, "2010": 4},
                                    "energy": {"2009": 4, "2010": 4}}}},
                        "secondary heating": {
                            "demand": {
                                "windows conduction": {
                                    "stock": "NA",
                                    "energy": {"2009": 5, "2010": 5}},
                                "windows solar": {
                                    "stock": "NA",
                                    "energy": {"2009": 6, "2010": 6}},
                                "infiltration": {
                                    "stock": "NA",
                                    "energy": {"2009": 10, "2010": 10}}},
                            "supply": {"non-specific": 7}},
                        "cooling": {
                            "demand": {
                                "windows conduction": {
                                    "stock": "NA",
                                    "energy": {"2009": 5, "2010": 5}},
                                "windows solar": {
                                    "stock": "NA",
                                    "energy": {"2009": 6, "2010": 6}},
                                "infiltration": {
                                    "stock": "NA",
                                    "energy": {"2009": 10, "2010": 10}}},
                            "supply": {
                                "central AC": {
                                    "stock": {"2009": 7, "2010": 7},
                                    "energy": {"2009": 7, "2010": 7}},
                                "room AC": {
                                    "stock": {"2009": 8, "2010": 8},
                                    "energy": {"2009": 8, "2010": 8}},
                                "ASHP": {
                                    "stock": {"2009": 9, "2010": 9},
                                    "energy": {"2009": 9, "2010": 9}},
                                "GSHP": {
                                    "stock": {"2009": 10, "2010": 10},
                                    "energy": {"2009": 10, "2010": 10}}}},
                        "lighting": {
                            "linear fluorescent (LED)": {
                                "stock": {"2009": 11, "2010": 11},
                                "energy": {"2009": 11, "2010": 11}},
                            "general service (LED)": {
                                "stock": {"2009": 12, "2010": 12},
                                "energy": {"2009": 12, "2010": 12}},
                            "reflector (LED)": {
                                "stock": {"2009": 13, "2010": 13},
                                "energy": {"2009": 13, "2010": 13}},
                            "external (LED)": {
                                "stock": {"2009": 14, "2010": 14},
                                "energy": {"2009": 14, "2010": 14}}},
                        "TVs": {
                            "TVs": {
                                "stock": {"2009": 99, "2010": 99},
                                "energy": {"2009": 9, "2010": 9}},
                            "set top box": {
                                "stock": {"2009": 99, "2010": 99},
                                "energy": {"2009": 999, "2010": 999}}
                            },
                        "computers": {
                            "desktop PC": {
                                "stock": {"2009": 44, "2010": 44},
                                "energy": {"2009": 4, "2010": 4}},
                            "laptop PC": {
                                "stock": {"2009": 55, "2010": 55},
                                "energy": {"2009": 5, "2010": 5}}
                            }},
                    "natural gas": {"water heating": {
                                    "stock": {"2009": 15, "2010": 15},
                                    "energy": {"2009": 15, "2010": 15}}}},
                "multi family home": {
                    "total square footage": {"2009": 700, "2010": 800},
                    "total homes": {"2009": 1000, "2010": 1000},
                    "new homes": {"2009": 100, "2010": 50},
                    "electricity": {
                        "heating": {
                            "demand": {
                                "windows conduction": {
                                    "stock": "NA",
                                    "energy": {"2009": 0, "2010": 0}},
                                "windows solar": {
                                    "stock": "NA",
                                    "energy": {"2009": 1, "2010": 1}}},
                            "supply": {
                                "resistance heat": {
                                    "stock": {"2009": 2, "2010": 2},
                                    "energy": {"2009": 2, "2010": 2}},
                                "ASHP": {
                                    "stock": {"2009": 3, "2010": 3},
                                    "energy": {"2009": 3, "2010": 3}},
                                "GSHP": {
                                    "stock": {"2009": 4, "2010": 4}}}},
                        "lighting": {
                            "linear fluorescent (LED)": {
                                "stock": {"2009": 11, "2010": 11},
                                "energy": {"2009": 11, "2010": 11}},
                            "general service (LED)": {
                                "stock": {"2009": 12, "2010": 12},
                                "energy": {"2009": 12, "2010": 12}},
                            "reflector (LED)": {
                                "stock": {"2009": 13, "2010": 13},
                                "energy": {"2009": 13, "2010": 13}},
                            "external (LED)": {
                                "stock": {"2009": 14, "2010": 14},
                                "energy": {"2009": 14, "2010": 14}}}}}},
            "AIA_CZ4": {
                "multi family home": {
                    "total square footage": {"2009": 900, "2010": 1000},
                    "total homes": {"2009": 1000, "2010": 1000},
                    "new homes": {"2009": 100, "2010": 50},
                    "electricity": {
                        "lighting": {
                            "linear fluorescent (LED)": {
                                "stock": {"2009": 11, "2010": 11},
                                "energy": {"2009": 11, "2010": 11}},
                            "general service (LED)": {
                                "stock": {"2009": 12, "2010": 12},
                                "energy": {"2009": 12, "2010": 12}},
                            "reflector (LED)": {
                                "stock": {"2009": 13, "2010": 13},
                                "energy": {"2009": 13, "2010": 13}},
                            "external (LED)": {
                                "stock": {"2009": 14, "2010": 14},
                                "energy": {"2009": 14, "2010": 14}}}}}}}
        cls.sample_cpl_in = {
            "AIA_CZ1": {
                "assembly": {
                    "electricity": {
                        "heating": {
                            "demand": {
                                "windows conduction": {
                                    "performance": {
                                        "typical": {"2009": 1, "2010": 1},
                                        "best": {"2009": 1, "2010": 1},
                                        "units": "R Value",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 1, "2010": 1},
                                        "best": {"2009": 1, "2010": 1},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 10, "2010": 10},
                                        "range": {"2009": 1, "2010": 1},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "windows solar": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "SHGC",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "lighting gain": 0}},
                        "cooling": {
                            "demand": {
                                "windows conduction": {
                                    "performance": {
                                        "typical": {"2009": 1, "2010": 1},
                                        "best": {"2009": 1, "2010": 1},
                                        "units": "R Value",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 1, "2010": 1},
                                        "best": {"2009": 1, "2010": 1},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 10, "2010": 10},
                                        "range": {"2009": 1, "2010": 1},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "windows solar": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "SHGC",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "lighting gain": 0}},
                        "lighting": {
                            "T5 F28": {
                                "performance": {
                                    "typical": {"2009": 14, "2010": 14},
                                    "best": {"2009": 14, "2010": 14},
                                    "units": "lm/W",
                                    "source":
                                    "EIA AEO"},
                                "installed cost": {
                                    "typical": {"2009": 14, "2010": 14},
                                    "best": {"2009": 14, "2010": 14},
                                    "units": "2014$/ft^2 floor",
                                    "source": "EIA AEO"},
                                "lifetime": {
                                    "average": {"2009": 140, "2010": 140},
                                    "range": {"2009": 14, "2010": 14},
                                    "units": "years",
                                    "source": "EIA AEO"},
                                "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}},
                        "PCs": 0,
                        "MELs": {
                            "distribution transformers": 0
                        }}},
                "single family home": {
                    "electricity": {
                        "heating": {
                            "demand": {
                                "windows conduction": {
                                    "performance": {
                                        "typical": {"2009": 1, "2010": 1},
                                        "best": {"2009": 1, "2010": 1},
                                        "units": "R Value",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 1, "2010": 1},
                                        "best": {"2009": 1, "2010": 1},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 10, "2010": 10},
                                        "range": {"2009": 1, "2010": 1},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "windows solar": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "SHGC",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "infiltration": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 3},
                                        "best": {"2009": 2, "2010": 3},
                                        "units": "ACH50",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}},
                            "supply": {
                                "resistance heat": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "ASHP": {
                                    "performance": {
                                        "typical": {"2009": 3, "2010": 3},
                                        "best": {"2009": 3, "2010": 3},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 3, "2010": 3},
                                        "best": {"2009": 3, "2010": 3},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 30, "2010": 30},
                                        "range": {"2009": 3, "2010": 3},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "GSHP": {
                                    "performance": {
                                        "typical": {"2009": 4, "2010": 4},
                                        "best": {"2009": 4, "2010": 4},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 4, "2010": 4},
                                        "best": {"2009": 4, "2010": 4},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 40, "2010": 40},
                                        "range": {"2009": 4, "2010": 4},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}}},
                        "secondary heating": {
                            "demand": {
                                "windows conduction": {
                                    "performance": {
                                        "typical": {"2009": 5, "2010": 5},
                                        "best": {"2009": 5, "2010": 5},
                                        "units": "R Value",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 5, "2010": 5},
                                        "best": {"2009": 5, "2010": 5},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 50, "2010": 50},
                                        "range": {"2009": 5, "2010": 5},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "windows solar": {
                                    "performance": {
                                        "typical": {"2009": 6, "2010": 6},
                                        "best": {"2009": 6, "2010": 6},
                                        "units": "SHGC",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 6, "2010": 6},
                                        "best": {"2009": 6, "2010": 6},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 60, "2010": 60},
                                        "range": {"2009": 6, "2010": 6},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "infiltration": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 3},
                                        "best": {"2009": 2, "2010": 3},
                                        "units": "ACH50",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}},
                            "supply": {
                                "non-specific": {
                                    "performance": {
                                        "typical": {"2009": 7, "2010": 7},
                                        "best": {"2009": 7, "2010": 7},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 7, "2010": 7},
                                        "best": {"2009": 7, "2010": 7},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 70, "2010": 70},
                                        "range": {"2009": 7, "2010": 7},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}}},
                        "cooling": {
                            "demand": {
                                "windows conduction": {
                                    "performance": {
                                        "typical": {
                                            "new": {"2009": 8, "2010": 8},
                                            "existing": {
                                                "2009": 8, "2010": 8}
                                            },
                                        "best": {"2009": 8, "2010": 8},
                                        "units": "R Value",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 8, "2010": 8},
                                        "best": {"2009": 8, "2010": 8},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 80, "2010": 80},
                                        "range": {"2009": 8, "2010": 8},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "windows solar": {
                                    "performance": {
                                        "typical": {"2009": 9, "2010": 9},
                                        "best": {"2009": 9, "2010": 9},
                                        "units": "SHGC",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 9, "2010": 9},
                                        "best": {"2009": 9, "2010": 9},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 90, "2010": 90},
                                        "range": {"2009": 9, "2010": 9},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "infiltration": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 3},
                                        "best": {"2009": 2, "2010": 3},
                                        "units": "ACH50",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}},
                            "supply": {
                                "central AC": {
                                    "performance": {
                                        "typical": {"2009": 10, "2010": 10},
                                        "best": {"2009": 10, "2010": 10},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 10, "2010": 10},
                                        "best": {"2009": 10, "2010": 10},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 100, "2010": 100},
                                        "range": {"2009": 10, "2010": 10},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "room AC": {
                                    "performance": {
                                        "typical": {"2009": 11, "2010": 11},
                                        "best": {"2009": 11, "2010": 11},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 11, "2010": 11},
                                        "best": {"2009": 11, "2010": 11},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 110, "2010": 110},
                                        "range": {"2009": 11, "2010": 11},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "ASHP": {
                                    "performance": {
                                        "typical": {"2009": 12, "2010": 12},
                                        "best": {"2009": 12, "2010": 12},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 12, "2010": 12},
                                        "best": {"2009": 12, "2010": 12},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 120, "2010": 120},
                                        "range": {"2009": 12, "2010": 12},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "GSHP": {
                                    "performance": {
                                        "typical": {"2009": 13, "2010": 13},
                                        "best": {"2009": 13, "2010": 13},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 13, "2010": 13},
                                        "best": {"2009": 13, "2010": 13},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 130, "2010": 130},
                                        "range": {"2009": 13, "2010": 13},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}}},
                        "lighting": {
                            "linear fluorescent (LED)": {
                                    "performance": {
                                        "typical": {"2009": 14, "2010": 14},
                                        "best": {"2009": 14, "2010": 14},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 14, "2010": 14},
                                        "best": {"2009": 14, "2010": 14},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {
                                            "2009": 140 * (3/24),
                                            "2010": 140 * (3/24)},
                                        "range": {"2009": 14, "2010": 14},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                            "general service (LED)": {
                                    "performance": {
                                        "typical": {"2009": 15, "2010": 15},
                                        "best": {"2009": 15, "2010": 15},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 15, "2010": 15},
                                        "best": {"2009": 15, "2010": 15},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {
                                            "2009": 150 * (3/24),
                                            "2010": 150 * (3/24)},
                                        "range": {"2009": 15, "2010": 15},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                            "reflector (LED)": {
                                    "performance": {
                                        "typical": {"2009": 16, "2010": 16},
                                        "best": {"2009": 16, "2010": 16},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 16, "2010": 16},
                                        "best": {"2009": 16, "2010": 16},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {
                                            "2009": 160 * (3/24),
                                            "2010": 160 * (3/24)},
                                        "range": {"2009": 16, "2010": 16},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                            "external (LED)": {
                                    "performance": {
                                        "typical": {"2009": 17, "2010": 17},
                                        "best": {"2009": 17, "2010": 17},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 17, "2010": 17},
                                        "best": {"2009": 17, "2010": 17},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {
                                            "2009": 170 * (3/24),
                                            "2010": 170 * (3/24)},
                                        "range": {"2009": 17, "2010": 17},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}},
                        "refrigeration": {
                            "performance": {
                                "typical": {"2009": 550, "2010": 550},
                                "best": {"2009": 450, "2010": 450},
                                "units": "kWh/yr",
                                "source":
                                "EIA AEO"},
                            "installed cost": {
                                "typical": {"2009": 300, "2010": 300},
                                "best": {"2009": 600, "2010": 600},
                                "units": "2010$/unit",
                                "source": "EIA AEO"},
                            "lifetime": {
                                "average": {"2009": 17, "2010": 17},
                                "range": {"2009": 6, "2010": 6},
                                "units": "years",
                                "source": "EIA AEO"},
                            "consumer choice": {
                                "competed market share": {
                                    "source": "EIA AEO",
                                    "model type": "logistic regression",
                                    "parameters": {
                                        "b1": {"2009": "NA", "2010": "NA"},
                                        "b2": {"2009": "NA",
                                               "2010": "NA"}}},
                                "competed market": {
                                    "source": "COBAM",
                                    "model type": "bass diffusion",
                                    "parameters": {
                                        "p": "NA",
                                        "q": "NA"}}}},
                        "TVs": {
                            "TVs": {
                                "performance": {
                                    "typical": {"2009": "NA", "2010": "NA"},
                                    "best": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "installed cost": {
                                    "typical": {"2009": "NA", "2010": "NA"},
                                    "best": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "lifetime": {
                                    "average": {"2009": "NA", "2010": "NA"},
                                    "range": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "consumer choice": {
                                    "competed market share": {
                                        "source": "EIA AEO",
                                        "model type":
                                            "logistic regression",
                                        "parameters": {
                                            "b1": {"2009": "NA",
                                                   "2010": "NA"},
                                            "b2": {"2009": "NA",
                                                   "2010": "NA"}}},
                                    "competed market": {
                                        "source": "COBAM",
                                        "model type": "bass diffusion",
                                        "parameters": {
                                            "p": "NA",
                                            "q": "NA"}}}},
                            "set top box": {
                                "performance": {
                                    "typical": {"2009": "NA", "2010": "NA"},
                                    "best": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "installed cost": {
                                    "typical": {"2009": "NA", "2010": "NA"},
                                    "best": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "lifetime": {
                                    "average": {"2009": "NA", "2010": "NA"},
                                    "range": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "consumer choice": {
                                    "competed market share": {
                                        "source": "EIA AEO",
                                        "model type":
                                            "logistic regression",
                                        "parameters": {
                                            "b1": {"2009": "NA",
                                                   "2010": "NA"},
                                            "b2": {"2009": "NA",
                                                   "2010": "NA"}}},
                                    "competed market": {
                                        "source": "COBAM",
                                        "model type": "bass diffusion",
                                        "parameters": {
                                            "p": "NA",
                                            "q": "NA"}}}}
                            },
                        "computers": {
                            "desktop PC": {
                                "performance": {
                                    "typical": {"2009": "NA", "2010": "NA"},
                                    "best": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "installed cost": {
                                    "typical": {"2009": "NA", "2010": "NA"},
                                    "best": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "lifetime": {
                                    "average": {"2009": "NA", "2010": "NA"},
                                    "range": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "consumer choice": {
                                    "competed market share": {
                                        "source": "EIA AEO",
                                        "model type":
                                            "logistic regression",
                                        "parameters": {
                                            "b1": {"2009": "NA",
                                                   "2010": "NA"},
                                            "b2": {"2009": "NA",
                                                   "2010": "NA"}}},
                                    "competed market": {
                                        "source": "COBAM",
                                        "model type": "bass diffusion",
                                        "parameters": {
                                            "p": "NA",
                                            "q": "NA"}}}},
                            "laptop PC": {
                                "performance": {
                                    "typical": {"2009": "NA", "2010": "NA"},
                                    "best": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "installed cost": {
                                    "typical": {"2009": "NA", "2010": "NA"},
                                    "best": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "lifetime": {
                                    "average": {"2009": "NA", "2010": "NA"},
                                    "range": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "consumer choice": {
                                    "competed market share": {
                                        "source": "EIA AEO",
                                        "model type":
                                            "logistic regression",
                                        "parameters": {
                                            "b1": {"2009": "NA",
                                                   "2010": "NA"},
                                            "b2": {"2009": "NA",
                                                   "2010": "NA"}}},
                                    "competed market": {
                                        "source": "COBAM",
                                        "model type": "bass diffusion",
                                        "parameters": {
                                            "p": "NA",
                                            "q": "NA"}}}}
                            },
                        "other (grid electric)": {
                            "freezers": {
                                "performance": {
                                    "typical": {"2009": 550, "2010": 550},
                                    "best": {"2009": 450, "2010": 450},
                                    "units": "kWh/yr",
                                    "source":
                                    "EIA AEO"},
                                "installed cost": {
                                    "typical": {"2009": 100, "2010": 100},
                                    "best": {"2009": 200, "2010": 200},
                                    "units": "2014$/unit",
                                    "source": "EIA AEO"},
                                "lifetime": {
                                    "average": {"2009": 15, "2010": 15},
                                    "range": {"2009": 3, "2010": 3},
                                    "units": "years",
                                    "source": "EIA AEO"},
                                "consumer choice": {
                                    "competed market share": {
                                        "source": "EIA AEO",
                                        "model type":
                                            "logistic regression",
                                        "parameters": {
                                            "b1": {"2009": "NA",
                                                   "2010": "NA"},
                                            "b2": {"2009": "NA",
                                                   "2010": "NA"}}},
                                    "competed market": {
                                        "source": "COBAM",
                                        "model type": "bass diffusion",
                                        "parameters": {
                                            "p": "NA",
                                            "q": "NA"}}}},
                            "other MELs": {
                                "performance": {
                                    "typical": {"2009": "NA", "2010": "NA"},
                                    "best": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "installed cost": {
                                    "typical": {"2009": "NA", "2010": "NA"},
                                    "best": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "lifetime": {
                                    "average": {"2009": "NA", "2010": "NA"},
                                    "range": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "consumer choice": {
                                    "competed market share": {
                                        "source": "EIA AEO",
                                        "model type":
                                            "logistic regression",
                                        "parameters": {
                                            "b1": {"2009": "NA",
                                                   "2010": "NA"},
                                            "b2": {"2009": "NA",
                                                   "2010": "NA"}}},
                                    "competed market": {
                                        "source": "COBAM",
                                        "model type": "bass diffusion",
                                        "parameters": {
                                            "p": "NA",
                                            "q": "NA"}}}}}},
                    "natural gas": {
                        "water heating": {
                            "performance": {
                                "typical": {"2009": 18, "2010": 18},
                                "best": {"2009": 18, "2010": 18},
                                "units": "EF",
                                "source":
                                "EIA AEO"},
                            "installed cost": {
                                "typical": {"2009": 18, "2010": 18},
                                "best": {"2009": 18, "2010": 18},
                                "units": "2014$/unit",
                                "source": "EIA AEO"},
                            "lifetime": {
                                "average": {"2009": 180, "2010": 180},
                                "range": {"2009": 18, "2010": 18},
                                "units": "years",
                                "source": "EIA AEO"},
                            "consumer choice": {
                                "competed market share": {
                                    "source": "EIA AEO",
                                    "model type": "logistic regression",
                                    "parameters": {
                                        "b1": {"2009": "NA", "2010": "NA"},
                                        "b2": {"2009": "NA",
                                               "2010": "NA"}}},
                                "competed market": {
                                    "source": "COBAM",
                                    "model type": "bass diffusion",
                                    "parameters": {
                                        "p": "NA",
                                        "q": "NA"}}}},
                        "heating": {
                            "demand": {
                                "windows conduction": {
                                    "performance": {
                                        "typical": {"2009": 1, "2010": 1},
                                        "best": {"2009": 1, "2010": 1},
                                        "units": "R Value",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 1, "2010": 1},
                                        "best": {"2009": 1, "2010": 1},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 10, "2010": 10},
                                        "range": {"2009": 1, "2010": 1},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "windows solar": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "SHGC",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "infiltration": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 3},
                                        "best": {"2009": 2, "2010": 3},
                                        "units": "ACH50",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}}},
                        "secondary heating": {
                            "demand": {
                                "windows conduction": {
                                    "performance": {
                                        "typical": {"2009": 5, "2010": 5},
                                        "best": {"2009": 5, "2010": 5},
                                        "units": "R Value",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 5, "2010": 5},
                                        "best": {"2009": 5, "2010": 5},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 50, "2010": 50},
                                        "range": {"2009": 5, "2010": 5},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "windows solar": {
                                    "performance": {
                                        "typical": {"2009": 6, "2010": 6},
                                        "best": {"2009": 6, "2010": 6},
                                        "units": "SHGC",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 6, "2010": 6},
                                        "best": {"2009": 6, "2010": 6},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 60, "2010": 60},
                                        "range": {"2009": 6, "2010": 6},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "infiltration": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 3},
                                        "best": {"2009": 2, "2010": 3},
                                        "units": "ACH50",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}}},
                        "cooling": {
                            "demand": {
                                "windows conduction": {
                                    "performance": {
                                        "typical": {"2009": 8, "2010": 8},
                                        "best": {"2009": 8, "2010": 8},
                                        "units": "R Value",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 8, "2010": 8},
                                        "best": {"2009": 8, "2010": 8},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 80, "2010": 80},
                                        "range": {"2009": 8, "2010": 8},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "windows solar": {
                                    "performance": {
                                        "typical": {"2009": 9, "2010": 9},
                                        "best": {"2009": 9, "2010": 9},
                                        "units": "SHGC",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 9, "2010": 9},
                                        "best": {"2009": 9, "2010": 9},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 90, "2010": 90},
                                        "range": {"2009": 9, "2010": 9},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "infiltration": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 3},
                                        "best": {"2009": 2, "2010": 3},
                                        "units": "ACH50",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}}}}},
                "multi family home": {
                    "electricity": {
                        "heating": {
                            "demand": {
                                "windows conduction": {
                                    "performance": {
                                        "typical": {"2009": 19, "2010": 19},
                                        "best": {"2009": 19, "2010": 19},
                                        "units": "R Value",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 19, "2010": 19},
                                        "best": {"2009": 19, "2010": 19},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 190, "2010": 190},
                                        "range": {"2009": 19, "2010": 19},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "windows solar": {
                                    "performance": {
                                        "typical": {"2009": 20, "2010": 20},
                                        "best": {"2009": 20, "2010": 20},
                                        "units": "SHGC",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 20, "2010": 20},
                                        "best": {"2009": 20, "2010": 20},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 200, "2010": 200},
                                        "range": {"2009": 20, "2010": 20},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}},
                            "supply": {
                                "resistance heat": {
                                    "performance": {
                                        "typical": {"2009": 21, "2010": 21},
                                        "best": {"2009": 21, "2010": 21},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 21, "2010": 21},
                                        "best": {"2009": 21, "2010": 21},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 210, "2010": 210},
                                        "range": {"2009": 21, "2010": 21},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "ASHP": {
                                    "performance": {
                                        "typical": {"2009": 22, "2010": 22},
                                        "best": {"2009": 22, "2010": 22},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 22, "2010": 22},
                                        "best": {"2009": 22, "2010": 22},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 220, "2010": 220},
                                        "range": {"2009": 22, "2010": 22},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "GSHP": {
                                    "performance": {
                                        "typical": {"2009": 23, "2010": 23},
                                        "best": {"2009": 23, "2010": 23},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 23, "2010": 23},
                                        "best": {"2009": 23, "2010": 23},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 230, "2010": 230},
                                        "range": {"2009": 23, "2010": 23},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}}},
                        "lighting": {
                            "linear fluorescent (LED)": {
                                    "performance": {
                                        "typical": {"2009": 24, "2010": 24},
                                        "best": {"2009": 24, "2010": 24},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 24, "2010": 24},
                                        "best": {"2009": 24, "2010": 24},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {
                                            "2009": 240 * (3/24),
                                            "2010": 240 * (3/24)},
                                        "range": {"2009": 24, "2010": 24},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                            "general service (LED)": {
                                    "performance": {
                                        "typical": {"2009": 25, "2010": 25},
                                        "best": {"2009": 25, "2010": 25},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 25, "2010": 25},
                                        "best": {"2009": 25, "2010": 25},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {
                                            "2009": 250 * (3/24),
                                            "2010": 250 * (3/24)},
                                        "range": {"2009": 25, "2010": 25},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                            "reflector (LED)": {
                                    "performance": {
                                        "typical": {"2009": 25, "2010": 25},
                                        "best": {"2009": 25, "2010": 25},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 25, "2010": 25},
                                        "best": {"2009": 25, "2010": 25},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {
                                            "2009": 250 * (3/24),
                                            "2010": 250 * (3/24)},
                                        "range": {"2009": 25, "2010": 25},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                            "external (LED)": {
                                    "performance": {
                                        "typical": {"2009": 25, "2010": 25},
                                        "best": {"2009": 25, "2010": 25},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 25, "2010": 25},
                                        "best": {"2009": 25, "2010": 25},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {
                                            "2009": 250 * (3/24),
                                            "2010": 250 * (3/24)},
                                        "range": {"2009": 25, "2010": 25},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}}}}},
            "AIA_CZ2": {
                "single family home": {
                    "electricity": {
                        "heating": {
                            "demand": {
                                "windows conduction": {
                                    "performance": {
                                        "typical": {"2009": 1, "2010": 1},
                                        "best": {"2009": 1, "2010": 1},
                                        "units": "R Value",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 1, "2010": 1},
                                        "best": {"2009": 1, "2010": 1},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 10, "2010": 10},
                                        "range": {"2009": 1, "2010": 1},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "windows solar": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "SHGC",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "infiltration": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 3},
                                        "best": {"2009": 2, "2010": 3},
                                        "units": "ACH50",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}},
                            "supply": {
                                "resistance heat": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "ASHP": {
                                    "performance": {
                                        "typical": {"2009": 3, "2010": 3},
                                        "best": {"2009": 3, "2010": 3},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 3, "2010": 3},
                                        "best": {"2009": 3, "2010": 3},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 30, "2010": 30},
                                        "range": {"2009": 3, "2010": 3},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "GSHP": {
                                    "performance": {
                                        "typical": {"2009": 4, "2010": 4},
                                        "best": {"2009": 4, "2010": 4},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 4, "2010": 4},
                                        "best": {"2009": 4, "2010": 4},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 40, "2010": 40},
                                        "range": {"2009": 4, "2010": 4},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}}},
                        "secondary heating": {
                            "demand": {
                                "windows conduction": {
                                    "performance": {
                                        "typical": {"2009": 5, "2010": 5},
                                        "best": {"2009": 5, "2010": 5},
                                        "units": "R Value",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 5, "2010": 5},
                                        "best": {"2009": 5, "2010": 5},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 50, "2010": 50},
                                        "range": {"2009": 5, "2010": 5},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "windows solar": {
                                    "performance": {
                                        "typical": {"2009": 6, "2010": 6},
                                        "best": {"2009": 6, "2010": 6},
                                        "units": "SHGC",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 6, "2010": 6},
                                        "best": {"2009": 6, "2010": 6},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 60, "2010": 60},
                                        "range": {"2009": 6, "2010": 6},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "infiltration": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 3},
                                        "best": {"2009": 2, "2010": 3},
                                        "units": "ACH50",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}},
                            "supply": {
                                "non-specific": {
                                    "performance": {
                                        "typical": {"2009": 7, "2010": 7},
                                        "best": {"2009": 7, "2010": 7},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 7, "2010": 7},
                                        "best": {"2009": 7, "2010": 7},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 70, "2010": 70},
                                        "range": {"2009": 7, "2010": 7},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}}},
                        "cooling": {
                            "demand": {
                                "windows conduction": {
                                    "performance": {
                                        "typical": {"2009": 8, "2010": 8},
                                        "best": {"2009": 8, "2010": 8},
                                        "units": "R Value",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 8, "2010": 8},
                                        "best": {"2009": 8, "2010": 8},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 80, "2010": 80},
                                        "range": {"2009": 8, "2010": 8},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "windows solar": {
                                    "performance": {
                                        "typical": {"2009": 9, "2010": 9},
                                        "best": {"2009": 9, "2010": 9},
                                        "units": "SHGC",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 9, "2010": 9},
                                        "best": {"2009": 9, "2010": 9},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 90, "2010": 90},
                                        "range": {"2009": 9, "2010": 9},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "infiltration": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 3},
                                        "best": {"2009": 2, "2010": 3},
                                        "units": "ACH50",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}},
                            "supply": {
                                "central AC": {
                                    "performance": {
                                        "typical": {"2009": 10, "2010": 10},
                                        "best": {"2009": 10, "2010": 10},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 10, "2010": 10},
                                        "best": {"2009": 10, "2010": 10},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 100, "2010": 100},
                                        "range": {"2009": 10, "2010": 10},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "room AC": {
                                    "performance": {
                                        "typical": {"2009": 11, "2010": 11},
                                        "best": {"2009": 11, "2010": 11},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 11, "2010": 11},
                                        "best": {"2009": 11, "2010": 11},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 110, "2010": 110},
                                        "range": {"2009": 11, "2010": 11},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "ASHP": {
                                    "performance": {
                                        "typical": {"2009": 12, "2010": 12},
                                        "best": {"2009": 12, "2010": 12},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 12, "2010": 12},
                                        "best": {"2009": 12, "2010": 12},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 120, "2010": 120},
                                        "range": {"2009": 12, "2010": 12},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "GSHP": {
                                    "performance": {
                                        "typical": {"2009": 13, "2010": 13},
                                        "best": {"2009": 13, "2010": 13},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 13, "2010": 13},
                                        "best": {"2009": 13, "2010": 13},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 130, "2010": 130},
                                        "range": {"2009": 13, "2010": 13},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}}},
                        "lighting": {
                            "linear fluorescent (LED)": {
                                    "performance": {
                                        "typical": {"2009": 14, "2010": 14},
                                        "best": {"2009": 14, "2010": 14},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 14, "2010": 14},
                                        "best": {"2009": 14, "2010": 14},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {
                                            "2009": 140 * (3/24),
                                            "2010": 140 * (3/24)},
                                        "range": {"2009": 14, "2010": 14},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                            "general service (LED)": {
                                    "performance": {
                                        "typical": {"2009": 15, "2010": 15},
                                        "best": {"2009": 15, "2010": 15},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 15, "2010": 15},
                                        "best": {"2009": 15, "2010": 15},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {
                                            "2009": 150 * (3/24),
                                            "2010": 150 * (3/24)},
                                        "range": {"2009": 15, "2010": 15},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                            "reflector (LED)": {
                                    "performance": {
                                        "typical": {"2009": 16, "2010": 16},
                                        "best": {"2009": 16, "2010": 16},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 16, "2010": 16},
                                        "best": {"2009": 16, "2010": 16},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {
                                            "2009": 160 * (3/24),
                                            "2010": 160 * (3/24)},
                                        "range": {"2009": 16, "2010": 16},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                            "external (LED)": {
                                    "performance": {
                                        "typical": {"2009": 17, "2010": 17},
                                        "best": {"2009": 17, "2010": 17},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 17, "2010": 17},
                                        "best": {"2009": 17, "2010": 17},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {
                                            "2009": 170 * (3/24),
                                            "2010": 170 * (3/24)},
                                        "range": {"2009": 17, "2010": 17},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}},
                        "TVs": {
                            "TVs": {
                                "performance": {
                                    "typical": {"2009": "NA", "2010": "NA"},
                                    "best": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "installed cost": {
                                    "typical": {"2009": "NA", "2010": "NA"},
                                    "best": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "lifetime": {
                                    "average": {"2009": "NA", "2010": "NA"},
                                    "range": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "consumer choice": {
                                    "competed market share": {
                                        "source": "EIA AEO",
                                        "model type":
                                            "logistic regression",
                                        "parameters": {
                                            "b1": {"2009": "NA",
                                                   "2010": "NA"},
                                            "b2": {"2009": "NA",
                                                   "2010": "NA"}}},
                                    "competed market": {
                                        "source": "COBAM",
                                        "model type": "bass diffusion",
                                        "parameters": {
                                            "p": "NA",
                                            "q": "NA"}}}},
                            "set top box": {
                                "performance": {
                                    "typical": {"2009": "NA", "2010": "NA"},
                                    "best": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "installed cost": {
                                    "typical": {"2009": "NA", "2010": "NA"},
                                    "best": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "lifetime": {
                                    "average": {"2009": "NA", "2010": "NA"},
                                    "range": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "consumer choice": {
                                    "competed market share": {
                                        "source": "EIA AEO",
                                        "model type":
                                            "logistic regression",
                                        "parameters": {
                                            "b1": {"2009": "NA",
                                                   "2010": "NA"},
                                            "b2": {"2009": "NA",
                                                   "2010": "NA"}}},
                                    "competed market": {
                                        "source": "COBAM",
                                        "model type": "bass diffusion",
                                        "parameters": {
                                            "p": "NA",
                                            "q": "NA"}}}}
                            },
                        "computers": {
                            "desktop PC": {
                                "performance": {
                                    "typical": {"2009": "NA", "2010": "NA"},
                                    "best": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "installed cost": {
                                    "typical": {"2009": "NA", "2010": "NA"},
                                    "best": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "lifetime": {
                                    "average": {"2009": "NA", "2010": "NA"},
                                    "range": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "consumer choice": {
                                    "competed market share": {
                                        "source": "EIA AEO",
                                        "model type":
                                            "logistic regression",
                                        "parameters": {
                                            "b1": {"2009": "NA",
                                                   "2010": "NA"},
                                            "b2": {"2009": "NA",
                                                   "2010": "NA"}}},
                                    "competed market": {
                                        "source": "COBAM",
                                        "model type": "bass diffusion",
                                        "parameters": {
                                            "p": "NA",
                                            "q": "NA"}}}},
                            "laptop PC": {
                                "performance": {
                                    "typical": {"2009": "NA", "2010": "NA"},
                                    "best": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "installed cost": {
                                    "typical": {"2009": "NA", "2010": "NA"},
                                    "best": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "lifetime": {
                                    "average": {"2009": "NA", "2010": "NA"},
                                    "range": {"2009": "NA", "2010": "NA"},
                                    "units": "NA",
                                    "source": "NA"},
                                "consumer choice": {
                                    "competed market share": {
                                        "source": "EIA AEO",
                                        "model type":
                                            "logistic regression",
                                        "parameters": {
                                            "b1": {"2009": "NA",
                                                   "2010": "NA"},
                                            "b2": {"2009": "NA",
                                                   "2010": "NA"}}},
                                    "competed market": {
                                        "source": "COBAM",
                                        "model type": "bass diffusion",
                                        "parameters": {
                                            "p": "NA",
                                            "q": "NA"}}}}
                            }},
                    "natural gas": {
                        "water heating": {
                                "performance": {
                                    "typical": {"2009": 18, "2010": 18},
                                    "best": {"2009": 18, "2010": 18},
                                    "units": "EF",
                                    "source":
                                    "EIA AEO"},
                                "installed cost": {
                                    "typical": {"2009": 18, "2010": 18},
                                    "best": {"2009": 18, "2010": 18},
                                    "units": "2014$/unit",
                                    "source": "EIA AEO"},
                                "lifetime": {
                                    "average": {"2009": 180, "2010": 180},
                                    "range": {"2009": 18, "2010": 18},
                                    "units": "years",
                                    "source": "EIA AEO"},
                                "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}}},
                "multi family home": {
                    "electricity": {
                        "heating": {
                            "demand": {
                                "windows conduction": {
                                    "performance": {
                                        "typical": {"2009": 19, "2010": 19},
                                        "best": {"2009": 19, "2010": 19},
                                        "units": "R Value",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 19, "2010": 19},
                                        "best": {"2009": 19, "2010": 19},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 190, "2010": 190},
                                        "range": {"2009": 19, "2010": 19},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "windows solar": {
                                    "performance": {
                                        "typical": {"2009": 20, "2010": 20},
                                        "best": {"2009": 20, "2010": 20},
                                        "units": "SHGC",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 20, "2010": 20},
                                        "best": {"2009": 20, "2010": 20},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 200, "2010": 200},
                                        "range": {"2009": 20, "2010": 20},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}},
                            "supply": {
                                "resistance heat": {
                                    "performance": {
                                        "typical": {"2009": 21, "2010": 21},
                                        "best": {"2009": 21, "2010": 21},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 21, "2010": 21},
                                        "best": {"2009": 21, "2010": 21},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 210, "2010": 210},
                                        "range": {"2009": 21, "2010": 21},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "ASHP": {
                                    "performance": {
                                        "typical": {"2009": 22, "2010": 22},
                                        "best": {"2009": 22, "2010": 22},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 22, "2010": 22},
                                        "best": {"2009": 22, "2010": 22},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 220, "2010": 220},
                                        "range": {"2009": 22, "2010": 22},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "GSHP": {
                                    "performance": {
                                        "typical": {"2009": 23, "2010": 23},
                                        "best": {"2009": 23, "2010": 23},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 23, "2010": 23},
                                        "best": {"2009": 23, "2010": 23},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 230, "2010": 230},
                                        "range": {"2009": 23, "2010": 23},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}}},
                        "lighting": {
                            "linear fluorescent (LED)": {
                                    "performance": {
                                        "typical": {"2009": 24, "2010": 24},
                                        "best": {"2009": 24, "2010": 24},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 24, "2010": 24},
                                        "best": {"2009": 24, "2010": 24},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {
                                            "2009": 240 * (3/24),
                                            "2010": 240 * (3/24)},
                                        "range": {"2009": 24, "2010": 24},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                            "general service (LED)": {
                                    "performance": {
                                        "typical": {"2009": 25, "2010": 25},
                                        "best": {"2009": 25, "2010": 25},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 25, "2010": 25},
                                        "best": {"2009": 25, "2010": 25},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {
                                            "2009": 250 * (3/24),
                                            "2010": 250 * (3/24)},
                                        "range": {"2009": 25, "2010": 25},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                            "reflector (LED)": {
                                    "performance": {
                                        "typical": {"2009": 25, "2010": 25},
                                        "best": {"2009": 25, "2010": 25},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 25, "2010": 25},
                                        "best": {"2009": 25, "2010": 25},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {
                                            "2009": 250 * (3/24),
                                            "2010": 250 * (3/24)},
                                        "range": {"2009": 25, "2010": 25},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                            "external (LED)": {
                                    "performance": {
                                        "typical": {"2009": 25, "2010": 25},
                                        "best": {"2009": 25, "2010": 25},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 25, "2010": 25},
                                        "best": {"2009": 25, "2010": 25},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {
                                            "2009": 250 * (3/24),
                                            "2010": 250 * (3/24)},
                                        "range": {"2009": 25, "2010": 25},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}}}}},
            "AIA_CZ4": {
                "multi family home": {
                    "electricity": {
                        "lighting": {
                            "linear fluorescent (LED)": {
                                    "performance": {
                                        "typical": {"2009": 24, "2010": 24},
                                        "best": {"2009": 24, "2010": 24},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 24, "2010": 24},
                                        "best": {"2009": 24, "2010": 24},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 240, "2010": 240},
                                        "range": {"2009": 24, "2010": 24},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                            "general service (LED)": {
                                    "performance": {
                                        "typical": {"2009": 25, "2010": 25},
                                        "best": {"2009": 25, "2010": 25},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 25, "2010": 25},
                                        "best": {"2009": 25, "2010": 25},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 250, "2010": 250},
                                        "range": {"2009": 25, "2010": 25},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                            "reflector (LED)": {
                                    "performance": {
                                        "typical": {"2009": 26, "2010": 26},
                                        "best": {"2009": 26, "2010": 26},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 26, "2010": 26},
                                        "best": {"2009": 26, "2010": 26},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 260, "2010": 260},
                                        "range": {"2009": 26, "2010": 26},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                            "external (LED)": {
                                    "performance": {
                                        "typical": {"2009": 27, "2010": 27},
                                        "best": {"2009": 27, "2010": 27},
                                        "units": "lm/W",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 27, "2010": 27},
                                        "best": {"2009": 27, "2010": 27},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 270, "2010": 270},
                                        "range": {"2009": 27, "2010": 27},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}}}}}}
        ok_measures_in = [{
            "name": "sample measure 1",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": {
                "AIA_CZ1": {"heating": 30,
                            "cooling": 25},
                "AIA_CZ2": {"heating": 30,
                            "cooling": 15}},
            "energy_efficiency_units": "COP",
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": "single family home",
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": ["heating", "cooling"],
            "technology": ["resistance heat", "ASHP", "GSHP", "room AC"]},
            {
            "name": "sample measure 2",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": {"new": 25, "existing": 25},
            "energy_efficiency_units": "EF",
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": "single family home",
            "climate_zone": ["AIA_CZ1"],
            "fuel_type": "natural gas",
            "fuel_switch_to": None,
            "end_use": "water heating",
            "technology": None},
            {
            "name": "sample measure 3",
            "markets": None,
            "installed_cost": 500,
            "cost_units": {
                "refrigeration": "2010$/unit",
                "other (grid electric)": "2014$/unit"},
            "energy_efficiency": 0.1,
            "energy_efficiency_units": "relative savings (constant)",
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": "single family home",
            "climate_zone": "AIA_CZ1",
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": ["refrigeration", "other (grid electric)"],
            "technology": [None, "freezers"]},
            {
            "name": "sample measure 4",
            "markets": None,
            "installed_cost": 10,
            "cost_units": "2014$/ft^2 floor",
            "energy_efficiency": {
                "windows conduction": 20,
                "windows solar": 1},
            "energy_efficiency_units": {
                "windows conduction": "R Value",
                "windows solar": "SHGC"},
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": "existing",
            "bldg_type": ["single family home",
                          "multi family home"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": "heating",
            "technology": [
                "windows conduction",
                "windows solar"]},
            {
            "name": "sample measure 5",
            "markets": None,
            "installed_cost": 10,
            "cost_units": "2014$/ft^2 floor",
            "energy_efficiency": 0.1,
            "energy_efficiency_units": "relative savings (constant)",
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "add-on",
            "structure_type": "existing",
            "bldg_type": ["single family home",
                          "multi family home"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": "lighting",
            "technology": "linear fluorescent (LED)"},
            {
            "name": "sample measure 6",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": {
                "primary": 25,
                "secondary": {
                    "heating": 0.4,
                    "secondary heating": 0.4,
                    "cooling": -0.4}},
            "energy_efficiency_units": {
                "primary": "lm/W",
                "secondary": "relative savings (constant)"},
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": ["single family home",
                          "multi family home"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": {
                "primary": "lighting",
                "secondary": [
                    "heating", "secondary heating",
                    "cooling"]},
            "technology": [
                "linear fluorescent (LED)",
                "general service (LED)",
                "external (LED)"]},
            {
            "name": "sample measure 7",
            "markets": None,
            "installed_cost": 10,
            "cost_units": "2014$/ft^2 floor",
            "energy_efficiency": {
                "windows conduction": 20,
                "windows solar": 1},
            "energy_efficiency_units": {
                "windows conduction": "R Value",
                "windows solar": "SHGC"},
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": ["single family home",
                          "multi family home"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": "heating",
            "technology": [
                "windows conduction",
                "windows solar"]},
            {
            "name": "sample measure 8",
            "markets": None,
            "installed_cost": 10,
            "cost_units": "2014$/ft^2 floor",
            "energy_efficiency": 1,
            "energy_efficiency_units": "SHGC",
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": "single family home",
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": "heating",
            "technology": "windows solar"},
            {
            "name": "sample measure 9",
            "markets": None,
            "installed_cost": 10,
            "cost_units": "2014$/ft^2 floor",
            "energy_efficiency": {
                "windows conduction": 10, "windows solar": 1},
            "energy_efficiency_units": {
                "windows conduction": "R Value",
                "windows solar": "SHGC"},
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": "single family home",
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": [
                "heating", "secondary heating",
                "cooling"],
            "technology": [
                "windows conduction", "windows solar"]},
            {
            "name": "sample measure 10",
            "markets": None,
            "installed_cost": 10,
            "cost_units": "2014$/ft^2 floor",
            "energy_efficiency": {
                "windows conduction": 0.4,
                "windows solar": 1},
            "energy_efficiency_units": {
                "windows conduction": "relative savings (constant)",
                "windows solar": "SHGC"},
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": "single family home",
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": ["heating", "secondary heating",
                        "cooling"],
            "technology": ["windows conduction",
                           "windows solar"]},
            {
            "name": "sample measure 11",  # Add heat/cool end uses later
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/ft^2 floor",
            "energy_efficiency": 25,
            "energy_efficiency_units": "lm/W",
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": "assembly",
            "climate_zone": "AIA_CZ1",
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": "lighting",
            "market_entry_year": None,
            "market_exit_year": None,
            "technology": [
                "T5 F28"]},
            {
            "name": "sample measure 12",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": 25,
            "energy_efficiency_units": "EF",
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": "new",
            "bldg_type": "single family home",
            "climate_zone": "AIA_CZ1",
            "fuel_type": "natural gas",
            "fuel_switch_to": None,
            "end_use": "water heating",
            "market_entry_year": None,
            "market_exit_year": None,
            "technology": None},
            {
            "name": "sample measure 13",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": 25,
            "energy_efficiency_units": "EF",
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": "existing",
            "bldg_type": "single family home",
            "climate_zone": "AIA_CZ1",
            "fuel_type": "natural gas",
            "fuel_switch_to": None,
            "end_use": "water heating",
            "technology": None},
            {
            "name": "sample measure 14",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": {
                "primary": 25,
                "secondary": {
                    "heating": 0.4,
                    "secondary heating": 0.4,
                    "cooling": -0.4}},
            "energy_efficiency_units": {
                "primary": "lm/W",
                "secondary": "relative savings (constant)"},
            "market_entry_year": 2010,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": ["single family home",
                          "multi family home"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": {
                "primary": "lighting",
                "secondary": ["heating", "secondary heating",
                              "cooling"]},
            "technology": [
                "linear fluorescent (LED)",
                "general service (LED)",
                "external (LED)"]},
            {
            "name": "sample measure 15",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": {
                "primary": 25,
                "secondary": {
                    "heating": 0.4,
                    "secondary heating": 0.4,
                    "cooling": -0.4}},
            "energy_efficiency_units": {
                "primary": "lm/W",
                "secondary": "relative savings (constant)"},
            "market_entry_year": None,
            "market_exit_year": 2010,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": ["single family home",
                          "multi family home"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": {
                "primary": "lighting",
                "secondary": ["heating", "secondary heating",
                              "cooling"]},
            "technology": [
                "linear fluorescent (LED)",
                "general service (LED)",
                "external (LED)"]},
            {
            "name": "sample measure 16",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": {
                "primary": 25,
                "secondary": {
                    "heating": 0.4,
                    "secondary heating": 0.4,
                    "cooling": -0.4}},
            "energy_efficiency_units": {
                "primary": "lm/W",
                "secondary": [
                    "relative savings (dynamic)", 2009]},
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": ["single family home",
                          "multi family home"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": {
                "primary": "lighting",
                "secondary": ["heating", "secondary heating",
                              "cooling"]},
            "technology": [
                "linear fluorescent (LED)",
                "general service (LED)",
                "external (LED)"]},
            {
            "name": "sample measure 17",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": {
                "new": 25, "existing": 25},
            "energy_efficiency_units": "EF",
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": "single family home",
            "climate_zone": ["AIA_CZ1"],
            "fuel_type": "natural gas",
            "fuel_switch_to": "electricity",
            "end_use": "water heating",
            "technology": None},
            {
            "name": "sample measure 18",
            "markets": None,
            "installed_cost": 11,
            "cost_units": "2014$/ft^2 floor",
            "energy_efficiency": 0.44,
            "energy_efficiency_units":
                "relative savings (constant)",
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "add-on",
            "structure_type": ["new", "existing"],
            "bldg_type": "assembly",
            "climate_zone": "AIA_CZ1",
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": "lighting",
            "market_entry_year": None,
            "market_exit_year": None,
            "technology": [
                "T5 F28"]},
            {
            "name": "sample measure 19",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": {
                "new": 25, "existing": 25},
            "energy_efficiency_units": "EF",
            "market_entry_year": None,
            "market_exit_year": None,
            "market_scaling_fractions": {
                "new": 0.25,
                "existing": 0.5},
            "market_scaling_fractions_source": {
                "new": {
                    "title": 'Sample title 1',
                    "author": 'Sample author 1',
                    "organization": 'Sample org 1',
                    "year": 'Sample year 1',
                    "URL": ('http://www.eia.gov/consumption/'
                            'commercial/data/2012/'),
                    "fraction_derivation": "Divide X by Y"},
                "existing": {
                    "title": 'Sample title 1',
                    "author": 'Sample author 1',
                    "organization": 'Sample org 1',
                    "year": 'Sample year 1',
                    "URL": ('http://www.eia.gov/consumption/'
                            'commercial/data/2012/'),
                    "fraction_derivation": "Divide X by Y"}},
            "product_lifetime": 1,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": "single family home",
            "climate_zone": "AIA_CZ1",
            "fuel_type": "natural gas",
            "fuel_switch_to": None,
            "end_use": "water heating",
            "technology": None},
            {
            "name": "sample measure 20",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": {
                "primary": 25,
                "secondary": {
                    "heating": 0.4,
                    "secondary heating": 0.4,
                    "cooling": -0.4}},
            "energy_efficiency_units": {
                "primary": "lm/W",
                "secondary": "relative savings (constant)"},
            "market_entry_year": None,
            "market_exit_year": None,
            "market_scaling_fractions": {
                "new": 0.25,
                "existing": 0.5},
            "market_scaling_fractions_source": {
                "new": {
                    "title": 'Sample title 2',
                    "author": 'Sample author 2',
                    "organization": 'Sample org 2',
                    "year": 'Sample year 2',
                    "URL": ('http://www.eia.gov/consumption/'
                            'commercial/data/2012/'),
                    "fraction_derivation": "Divide X by Y"},
                "existing": {
                    "title": 'Sample title 2',
                    "author": 'Sample author 2',
                    "organization": 'Sample org 2',
                    "year": 'Sample year 2',
                    "URL": ('http://www.eia.gov/consumption/'
                            'residential/data/2009/'),
                    "fraction_derivation": "Divide X by Y"}},
            "product_lifetime": 1,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": ["single family home",
                          "multi family home"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": {
                "primary": "lighting",
                "secondary": ["heating", "secondary heating",
                              "cooling"]},
            "technology": [
                "linear fluorescent (LED)",
                "general service (LED)",
                "external (LED)"]},
            {
            "name": "sample measure 21",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "$/ft^2 floor",
            "energy_efficiency": 0.25,
            "energy_efficiency_units": "relative savings (constant)",
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "add-on",
            "structure_type": ["new", "existing"],
            "bldg_type": "assembly",
            "climate_zone": "AIA_CZ1",
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": ["PCs", "MELs"],
            "market_entry_year": None,
            "market_exit_year": None,
            "technology": [None, "distribution transformers"]},
            {
            "name": "sample measure 22",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "$/unit",
            "energy_efficiency": 0.5,
            "energy_efficiency_units": "relative savings (constant)",
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "add-on",
            "structure_type": ["new", "existing"],
            "bldg_type": "single family home",
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": ["TVs", "computers", "other (grid electric)"],
            "market_entry_year": None,
            "market_exit_year": None,
            "technology": ["TVs", "desktop PC", "laptop PC", "other MELs"]},
            {
            "name": "sample measure 23",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/ft^2 floor",
            "energy_efficiency": 25,
            "energy_efficiency_units": "lm/W",
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": "assembly",
            "climate_zone": "AIA_CZ1",
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": "lighting",
            "market_entry_year": None,
            "market_exit_year": None,
            "technology": "T5 F28"}]
        cls.ok_tpmeas_fullchk_in = [
            ecm_prep.Measure(
                handyvars, **x) for x in ok_measures_in[0:5]]
        cls.ok_tpmeas_partchk_in = [
            ecm_prep.Measure(
                handyvars, **x) for x in ok_measures_in[5:22]]
        cls.ok_mapmeas_partchk_in = [
            ecm_prep.Measure(
                handyvars, **x) for x in ok_measures_in[22:]]
        ok_distmeas_in = [{
            "name": "distrib measure 1",
            "markets": None,
            "installed_cost": ["normal", 25, 5],
            "cost_units": "2014$/unit",
            "energy_efficiency": {
                "AIA_CZ1": {
                    "heating": ["normal", 30, 1],
                    "cooling": ["normal", 25, 2]},
                "AIA_CZ2": {
                    "heating": 30,
                    "cooling": ["normal", 15, 4]}},
            "energy_efficiency_units": "COP",
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": ["single family home"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": ["heating", "cooling"],
            "technology": ["resistance heat", "ASHP", "GSHP", "room AC"]},
            {
            "name": "distrib measure 2",
            "markets": None,
            "installed_cost": ["lognormal", 3.22, 0.06],
            "cost_units": "2014$/unit",
            "energy_efficiency": ["normal", 25, 5],
            "energy_efficiency_units": "EF",
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": ["normal", 1, 1],
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": ["single family home"],
            "climate_zone": ["AIA_CZ1"],
            "fuel_type": ["natural gas"],
            "fuel_switch_to": None,
            "end_use": "water heating",
            "technology": None},
            {
            "name": "distrib measure 3",
            "markets": None,
            "installed_cost": ["normal", 10, 5],
            "cost_units": "2014$/ft^2 floor",
            "energy_efficiency": {
                "windows conduction": [
                    "lognormal", 2.29, 0.14],
                "windows solar": [
                    "normal", 1, 0.1]},
            "energy_efficiency_units": {
                "windows conduction": "R Value",
                "windows solar": "SHGC"},
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": ["single family home"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": [
                "heating", "secondary heating", "cooling"],
            "technology": [
                "windows conduction", "windows solar"]}]
        cls.ok_distmeas_in = [
            ecm_prep.Measure(
                handyvars, **x) for x in ok_distmeas_in]
        ok_partialmeas_in = [{
            "name": "partial measure 1",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": 25,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "energy_efficiency_units": "COP",
            "market_entry_year": None,
            "market_exit_year": None,
            "bldg_type": ["single family home"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": "cooling",
            "technology": ["resistance heat", "ASHP"]},
            {
            "name": "partial measure 2",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": 25,
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "energy_efficiency_units": "COP",
            "bldg_type": ["single family home"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": ["heating", "cooling"],
            "technology": [
                "linear fluorescent (LED)",
                "general service (LED)",
                "external (LED)", "GSHP", "ASHP"]}]
        cls.ok_partialmeas_in = [
            ecm_prep.Measure(
                handyvars, **x) for x in ok_partialmeas_in]
        failmeas_in = [{
            "name": "fail measure 1",
            "markets": None,
            "installed_cost": 10,
            "cost_units": "2014$/unit",
            "energy_efficiency": 10,
            "energy_efficiency_units": "COP",
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": "single family home",
            "climate_zone": ["AIA_CZ19", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": "cooling",
            "technology": "resistance heat"},
            {
            "name": "fail measure 2",
            "markets": None,
            "installed_cost": 10,
            "cost_units": "2014$/unit",
            "energy_efficiency": {
                "AIA_CZ1": {
                    "heating": 30, "cooling": 25},
                "AIA_CZ2": {
                    "heating": 30, "cooling": 15}},
            "energy_efficiency_units": "COP",
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": "single family homer",
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": ["heating", "cooling"],
            "technology": [
                "linear fluorescent (LED)",
                "general service (LED)",
                "external (LED)"]},
            {
            "name": "fail measure 3",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": {
                "primary": 25, "secondary": None},
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["newer", "existing"],
            "energy_efficiency_units": {
                "primary": "lm/W", "secondary": None},
            "market_entry_year": None,
            "market_exit_year": None,
            "bldg_type": "single family home",
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "natural gas",
            "fuel_switch_to": None,
            "end_use": {
                "primary": "lighting",
                "secondary": [
                    "heating", "secondary heating",
                    "cooling"]},
            "technology": [
                "linear fluorescent (LED)",
                "general service (LED)",
                "external (LED)"]},
            {
            "name": "fail measure 4",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": {
                "primary": 25, "secondary": None},
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "energy_efficiency_units": {
                "primary": "lm/W", "secondary": None},
            "market_entry_year": None,
            "market_exit_year": None,
            "bldg_type": "single family home",
            "climate_zone": "AIA_CZ1",
            "fuel_type": "solar",
            "fuel_switch_to": None,
            "end_use": {
                "primary": "lighting",
                "secondary": [
                    "heating", "secondary heating",
                    "cooling"]},
            "technology": [
                "linear fluorescent (LED)",
                "general service (LED)",
                "external (LED)"]},
            {
            "name": "fail measure 5",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/ft^2 floor",
            "energy_efficiency": 0.25,
            "energy_efficiency_units": "relative savings (constant)",
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": "assembly",
            "climate_zone": "AIA_CZ1",
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": ["PCs", "MELs"],
            "market_entry_year": None,
            "market_exit_year": None,
            "technology": [None, "distribution transformers"]}]
        cls.failmeas_inputs_in = [
            ecm_prep.Measure(
                handyvars, **x) for x in failmeas_in[0:-1]]
        cls.failmeas_missing_in = ecm_prep.Measure(
            handyvars, **failmeas_in[-1])
        warnmeas_in = [{
            "name": "warn measure 1",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": {
                "primary": 25,
                "secondary": {
                    "heating": 0.4,
                    "secondary heating": 0.4,
                    "cooling": -0.4}},
            "energy_efficiency_units": {
                "primary": "lm/W",
                "secondary": "relative savings (constant)"},
            "market_entry_year": None,
            "market_exit_year": None,
            "market_scaling_fractions": {
                "new": 0.25,
                "existing": 0.5},
            "market_scaling_fractions_source": {
                "new": {
                    "title": None,
                    "author": None,
                    "organization": None,
                    "year": None,
                    "URL": None,
                    "fraction_derivation": None},
                "existing": {
                    "title": None,
                    "author": None,
                    "organization": None,
                    "year": None,
                    "URL": None,
                    "fraction_derivation": None}},
            "product_lifetime": 1,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": [
                "single family home",
                "multi family home"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": {
                "primary": "lighting",
                "secondary": [
                    "heating", "secondary heating",
                    "cooling"]},
            "technology": [
                "linear fluorescent (LED)",
                "general service (LED)",
                "external (LED)"]},
            {
            "name": "warn measure 2",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": {
                "primary": 25,
                "secondary": {
                    "heating": 0.4,
                    "secondary heating": 0.4,
                    "cooling": -0.4}},
            "energy_efficiency_units": {
                "primary": "lm/W",
                "secondary": "relative savings (constant)"},
            "market_entry_year": None,
            "market_exit_year": None,
            "market_scaling_fractions": {
                "new": 0.25,
                "existing": 0.5},
            "market_scaling_fractions_source": {
                "new": {
                    "title": "Sample title",
                    "author": "Sample author",
                    "organization": "Sample organization",
                    "year": "http://www.sciencedirectcom",
                    "URL": "some BS",
                    "fraction_derivation": None},
                "existing": {
                    "title": "Sample title",
                    "author": "Sample author",
                    "organization": "Sample organization",
                    "year": "Sample year",
                    "URL": "http://www.sciencedirect.com",
                    "fraction_derivation": None}},
            "product_lifetime": 1,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": [
                "single family home",
                "multi family home"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": {
                "primary": "lighting",
                "secondary": [
                    "heating", "secondary heating",
                    "cooling"]},
            "technology": [
                "linear fluorescent (LED)",
                "general service (LED)",
                "external (LED)"]},
            {
            "name": "warn measure 3",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": {
                "primary": 25,
                "secondary": {
                    "heating": 0.4,
                    "secondary heating": 0.4,
                    "cooling": -0.4}},
            "energy_efficiency_units": {
                "primary": "lm/W",
                "secondary": "relative savings (constant)"},
            "market_entry_year": None,
            "market_exit_year": None,
            "market_scaling_fractions": {
                "new": 0.25,
                "existing": 0.5},
            "market_scaling_fractions_source": {
                "new": {
                    "title": "Sample title",
                    "author": None,
                    "organization": "Sample organization",
                    "year": "Sample year",
                    "URL": "https://bpd.lbl.gov/",
                    "fraction_derivation": "Divide X by Y"},
                "existing": {
                    "title": "Sample title",
                    "author": None,
                    "organization": "Sample organization",
                    "year": "Sample year",
                    "URL": "https://cms.doe.gov/data/green-button",
                    "fraction_derivation": "Divide X by Y"}},
            "product_lifetime": 1,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": [
                "single family home",
                "multi family home"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": {
                "primary": "lighting",
                "secondary": [
                    "heating", "secondary heating",
                    "cooling"]},
            "technology": [
                "linear fluorescent (LED)",
                "general service (LED)",
                "external (LED)"]}]
        cls.warnmeas_in = [
            ecm_prep.Measure(
                handyvars, **x) for x in warnmeas_in]
        cls.ok_tpmeas_fullchk_msegout = [{
            "stock": {
                "total": {
                    "all": {"2009": 72, "2010": 72},
                    "measure": {"2009": 72, "2010": 72}},
                "competed": {
                    "all": {"2009": 72, "2010": 72},
                    "measure": {"2009": 72, "2010": 72}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 229.68, "2010": 230.4},
                    "efficient": {"2009": 117.0943, "2010": 117.4613}},
                "competed": {
                    "baseline": {"2009": 229.68, "2010": 230.4},
                    "efficient": {"2009": 117.0943, "2010": 117.4613}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 13056.63, "2010": 12941.16},
                    "efficient": {"2009": 6656.461, "2010": 6597.595}},
                "competed": {
                    "baseline": {"2009": 13056.63, "2010": 12941.16},
                    "efficient": {"2009": 6656.461, "2010": 6597.595}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 710, "2010": 710},
                        "efficient": {"2009": 1800, "2010": 1800}},
                    "competed": {
                        "baseline": {"2009": 710, "2010": 710},
                        "efficient": {"2009": 1800, "2010": 1800}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 2328.955, "2010": 2227.968},
                        "efficient": {"2009": 1187.336, "2010": 1135.851}},
                    "competed": {
                        "baseline": {"2009": 2328.955, "2010": 2227.968},
                        "efficient": {"2009": 1187.336, "2010": 1135.851}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 430868.63, "2010": 427058.3},
                        "efficient": {"2009": 219663.21, "2010": 217720.65}},
                    "competed": {
                        "baseline": {"2009": 430868.63, "2010": 427058.3},
                        "efficient": {"2009": 219663.21, "2010": 217720.65}}}},
            "lifetime": {"baseline": {"2009": 98.61, "2010": 98.61},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 15, "2010": 15},
                    "measure": {"2009": 15, "2010": 15}},
                "competed": {
                    "all": {"2009": 15, "2010": 15},
                    "measure": {"2009": 15, "2010": 15}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 15.15, "2010": 15.15},
                    "efficient": {"2009": 10.908, "2010": 10.908}},
                "competed": {
                    "baseline": {"2009": 15.15, "2010": 15.15},
                    "efficient": {"2009": 10.908, "2010": 10.908}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 856.2139, "2010": 832.0021},
                    "efficient": {"2009": 616.474, "2010": 599.0415}},
                "competed": {
                    "baseline": {"2009": 856.2139, "2010": 832.0021},
                    "efficient": {"2009": 616.474, "2010": 599.0415}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 270, "2010": 270},
                        "efficient": {"2009": 375, "2010": 375}},
                    "competed": {
                        "baseline": {"2009": 270, "2010": 270},
                        "efficient": {"2009": 375, "2010": 375}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 170.892, "2010": 163.317},
                        "efficient": {"2009": 123.0422, "2010": 117.5882}},
                    "competed": {
                        "baseline": {"2009": 170.892, "2010": 163.317},
                        "efficient": {"2009": 123.0422, "2010": 117.5882}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 28255.06, "2010": 27456.07},
                        "efficient": {"2009": 20343.64, "2010": 19768.37}},
                    "competed": {
                        "baseline": {"2009": 28255.06, "2010": 27456.07},
                        "efficient": {"2009": 20343.64, "2010": 19768.37}}}},
            "lifetime": {"baseline": {"2009": 180, "2010": 180},
                         "measure": 1}},
                        {
            "stock": {
                "total": {
                    "all": {"2009": 333, "2010": 333},
                    "measure": {"2009": 333, "2010": 333}},
                "competed": {
                    "all": {"2009": 333, "2010": 333},
                    "measure": {"2009": 333, "2010": 333}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 1062.27, "2010": 1065.6},
                    "efficient": {"2009": 956.043, "2010": 959.04}},
                "competed": {
                    "baseline": {"2009": 1062.27, "2010": 1065.6},
                    "efficient": {"2009": 956.043, "2010": 959.04}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 60386.89, "2010": 59852.87},
                    "efficient": {"2009": 54348.2, "2010": 53867.58}},
                "competed": {
                    "baseline": {"2009": 60386.89, "2010": 59852.87},
                    "efficient": {"2009": 54348.2, "2010": 53867.58}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 55500, "2010": 55500},
                        "efficient": {"2009": 166500, "2010": 166500}},
                    "competed": {
                        "baseline": {"2009": 55500, "2010": 55500},
                        "efficient": {"2009": 166500, "2010": 166500}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 10771.42, "2010": 10304.35},
                        "efficient": {"2009": 9694.276, "2010": 9273.917}},
                    "competed": {
                        "baseline": {"2009": 10771.42, "2010": 10304.35},
                        "efficient": {"2009": 9694.276, "2010": 9273.917}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 1992767.41, "2010": 1975144.64},
                        "efficient": {"2009": 1793490.67, "2010": 1777630.18}},
                    "competed": {
                        "baseline": {"2009": 1992767.41, "2010": 1975144.64},
                        "efficient": {
                            "2009": 1793490.67, "2010": 1777630.18}}}},
            "lifetime": {"baseline": {"2009": 15.67, "2010": 15.67},
                         "measure": 1}}]
        # Correct consumer choice dict outputs
        compete_choice_val = [{
            "b1": {"2009": -0.01, "2010": -0.01},
            "b2": {"2009": -0.12, "2010": -0.12}},
            {
            "b1": {"2009": -0.01 * handyvars.res_typ_sf_household[
                    "single family home"],
                   "2010": -0.01 * handyvars.res_typ_sf_household[
                   "single family home"]},
            "b2": {"2009": -0.12 * handyvars.res_typ_sf_household[
                    "single family home"],
                   "2010": -0.12 * handyvars.res_typ_sf_household[
                   "single family home"]}},
            {
            "b1": {"2009": -0.01 * handyvars.res_typ_sf_household[
                    "multi family home"],
                   "2010": -0.01 * handyvars.res_typ_sf_household[
                    "multi family home"]},
            "b2": {"2009": -0.12 * handyvars.res_typ_sf_household[
                    "multi family home"],
                   "2010": -0.12 * handyvars.res_typ_sf_household[
                   "multi family home"]}},
            {
            "b1": {
                "2009": -0.01 * handyvars.res_typ_sf_household[
                    "single family home"] /
                handyvars.res_typ_units_household[
                    "lighting"]["single family home"],
                "2010": -0.01 * handyvars.res_typ_sf_household[
                   "single family home"] /
                handyvars.res_typ_units_household[
                    "lighting"]["single family home"]},
            "b2": {
                "2009": -0.12 * handyvars.res_typ_sf_household[
                    "single family home"] /
                handyvars.res_typ_units_household[
                    "lighting"]["single family home"],
                "2010": -0.12 * handyvars.res_typ_sf_household[
                   "single family home"] /
                handyvars.res_typ_units_household[
                    "lighting"]["single family home"]}},
            {
            "b1": {
                "2009": -0.01 * handyvars.res_typ_sf_household[
                    "multi family home"] /
                handyvars.res_typ_units_household[
                    "lighting"]["multi family home"],
                "2010": -0.01 * handyvars.res_typ_sf_household[
                    "multi family home"] /
                handyvars.res_typ_units_household[
                    "lighting"]["multi family home"]},
            "b2": {
                "2009": -0.12 * handyvars.res_typ_sf_household[
                    "multi family home"] /
                handyvars.res_typ_units_household[
                    "lighting"]["multi family home"],
                "2010": -0.12 * handyvars.res_typ_sf_household[
                   "multi family home"] /
                handyvars.res_typ_units_household[
                    "lighting"]["multi family home"]}}]
        cls.ok_tpmeas_fullchk_competechoiceout = [{
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'electricity', 'heating', 'supply', "
             "'resistance heat', 'new')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'electricity', 'heating', 'supply', "
             "'ASHP', 'new')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'electricity', 'heating', 'supply', "
             "'GSHP', 'new')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'electricity', 'cooling', 'supply', "
             "'ASHP', 'new')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'electricity', 'cooling', 'supply', "
             "'GSHP', 'new')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'electricity', 'cooling', 'supply', "
             "'room AC', 'new')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ2', 'single family home', "
             "'electricity', 'heating', 'supply', "
             "'resistance heat', 'new')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ2', 'single family home', "
             "'electricity', 'heating', 'supply', "
             "'ASHP', 'new')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ2', 'single family home', "
             "'electricity', 'heating', 'supply', "
             "'GSHP', 'new')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ2', 'single family home', "
             "'electricity', 'cooling', 'supply', "
             "'ASHP', 'new')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ2', 'single family home', "
             "'electricity', 'cooling', 'supply', "
             "'GSHP', 'new')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ2', 'single family home', "
             "'electricity', 'cooling', 'supply', "
             "'room AC', 'new')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'electricity', 'heating', 'supply', "
             "'resistance heat', 'existing')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'electricity', 'heating', 'supply', "
             "'ASHP', 'existing')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'electricity', 'heating', 'supply', "
             "'GSHP', 'existing')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'electricity', 'cooling', 'supply', "
             "'ASHP', 'existing')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'electricity', 'cooling', 'supply', "
             "'GSHP', 'existing')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'electricity', 'cooling', 'supply', "
             "'room AC', 'existing')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ2', 'single family home', "
             "'electricity', 'heating', 'supply', "
             "'resistance heat', 'existing')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ2', 'single family home', "
             "'electricity', 'heating', 'supply', "
             "'ASHP', 'existing')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ2', 'single family home', "
             "'electricity', 'heating', 'supply', "
             "'GSHP', 'existing')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ2', 'single family home', "
             "'electricity', 'cooling', 'supply', "
             "'ASHP', 'existing')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ2', 'single family home', "
             "'electricity', 'cooling', 'supply', "
             "'GSHP', 'existing')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ2', 'single family home', "
             "'electricity', 'cooling', 'supply', "
             "'room AC', 'existing')"): compete_choice_val[0]},
            {
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'natural gas', 'water heating', "
             "None, 'new')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'natural gas', 'water heating', "
             "None, 'existing')"): compete_choice_val[0]},
            {
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'electricity', 'other (grid electric)', "
             "'freezers', 'new')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'electricity', 'other (grid electric)', "
             "'freezers', 'existing')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'electricity', 'refrigeration', None, "
             "'existing')"): compete_choice_val[0],
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'electricity', 'refrigeration', None, "
             "'new')"): compete_choice_val[0]},
            {
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'electricity', 'heating', 'demand', 'windows', "
             "'existing')"): compete_choice_val[1],
            ("('primary', 'AIA_CZ2', 'single family home', "
             "'electricity', 'heating', 'demand', 'windows', "
             "'existing')"): compete_choice_val[1],
            ("('primary', 'AIA_CZ1', 'multi family home', "
             "'electricity', 'heating', 'demand', 'windows', "
             "'existing')"): compete_choice_val[2],
            ("('primary', 'AIA_CZ2', 'multi family home', "
             "'electricity', 'heating', 'demand', 'windows', "
             "'existing')"): compete_choice_val[2]},
            {
            ("('primary', 'AIA_CZ1', 'single family home', "
             "'electricity', 'lighting', 'linear fluorescent (LED)', "
             "'existing')"): compete_choice_val[3],
            ("('primary', 'AIA_CZ2', 'single family home', "
             "'electricity', 'lighting', 'linear fluorescent (LED)', "
             "'existing')"): compete_choice_val[3],
            ("('primary', 'AIA_CZ1', 'multi family home', "
             "'electricity', 'lighting', 'linear fluorescent (LED)', "
             "'existing')"): compete_choice_val[4],
            ("('primary', 'AIA_CZ2', 'multi family home', "
             "'electricity', 'lighting', 'linear fluorescent (LED)', "
             "'existing')"): compete_choice_val[4]}]
        cls.ok_tpmeas_fullchk_msegadjout = [{
            "sub-market": {
                "original energy (total)": {},
                "adjusted energy (sub-market)": {}},
            "stock-and-flow": {
                "original energy (total)": {},
                "adjusted energy (previously captured)": {},
                "adjusted energy (competed)": {},
                "adjusted energy (competed and captured)": {}},
            "market share": {
                "original energy (total captured)": {},
                "original energy (competed and captured)": {},
                "adjusted energy (total captured)": {},
                "adjusted energy (competed and captured)": {}}},
            {
            "sub-market": {
                "original energy (total)": {},
                "adjusted energy (sub-market)": {}},
            "stock-and-flow": {
                "original energy (total)": {},
                "adjusted energy (previously captured)": {},
                "adjusted energy (competed)": {},
                "adjusted energy (competed and captured)": {}},
            "market share": {
                "original energy (total captured)": {},
                "original energy (competed and captured)": {},
                "adjusted energy (total captured)": {},
                "adjusted energy (competed and captured)": {}}},
            {
            "sub-market": {
                "original energy (total)": {},
                "adjusted energy (sub-market)": {}},
            "stock-and-flow": {
                "original energy (total)": {},
                "adjusted energy (previously captured)": {},
                "adjusted energy (competed)": {},
                "adjusted energy (competed and captured)": {}},
            "market share": {
                "original energy (total captured)": {},
                "original energy (competed and captured)": {},
                "adjusted energy (total captured)": {},
                "adjusted energy (competed and captured)": {}}}]
        cls.ok_tpmeas_fullchk_supplydemandout = [{
            "savings": {
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'resistance heat', 'new')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'ASHP', 'new')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'GSHP', 'new')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'ASHP', 'new')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'GSHP', 'new')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'room AC', 'new')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'resistance heat', 'new')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'ASHP', 'new')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'GSHP', 'new')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'ASHP', 'new')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'GSHP', 'new')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'room AC', 'new')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'resistance heat', 'existing')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'ASHP', 'existing')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'GSHP', 'existing')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'ASHP', 'existing')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'GSHP', 'existing')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'room AC', 'existing')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'resistance heat', 'existing')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'ASHP', 'existing')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'GSHP', 'existing')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'ASHP', 'existing')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'GSHP', 'existing')"): {"2009": 0, "2010": 0},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'room AC', 'existing')"): {"2009": 0, "2010": 0}},
            "total": {
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'resistance heat', 'new')"): {
                    "2009": 28.71, "2010": 28.80},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'ASHP', 'new')"): {"2009": 28.71, "2010": 28.80},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'GSHP', 'new')"): {"2009": 28.71, "2010": 28.80},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'ASHP', 'new')"): {"2009": 108.46, "2010": 108.8},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'GSHP', 'new')"): {"2009": 108.46, "2010": 108.8},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'room AC', 'new')"): {"2009": 108.46, "2010": 108.8},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'resistance heat', 'new')"): {
                    "2009": 28.71, "2010": 28.80},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'ASHP', 'new')"): {"2009": 28.71, "2010": 28.80},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'GSHP', 'new')"): {"2009": 28.71, "2010": 28.80},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'ASHP', 'new')"): {"2009": 108.46, "2010": 108.8},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'GSHP', 'new')"): {"2009": 108.46, "2010": 108.8},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'room AC', 'new')"): {"2009": 108.46, "2010": 108.8},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'resistance heat', 'existing')"): {
                    "2009": 28.71, "2010": 28.80},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'ASHP', 'existing')"): {"2009": 28.71, "2010": 28.80},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'GSHP', 'existing')"): {"2009": 28.71, "2010": 28.80},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'ASHP', 'existing')"): {"2009": 108.46, "2010": 108.8},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'GSHP', 'existing')"): {"2009": 108.46, "2010": 108.8},
                ("('primary', 'AIA_CZ1', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'room AC', 'existing')"): {"2009": 108.46, "2010": 108.8},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'resistance heat', 'existing')"): {
                    "2009": 28.71, "2010": 28.80},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'ASHP', 'existing')"): {"2009": 28.71, "2010": 28.80},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'heating', 'supply', "
                 "'GSHP', 'existing')"): {"2009": 28.71, "2010": 28.80},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'ASHP', 'existing')"): {"2009": 108.46, "2010": 108.8},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'GSHP', 'existing')"): {"2009": 108.46, "2010": 108.8},
                ("('primary', 'AIA_CZ2', 'single family home', "
                 "'electricity', 'cooling', 'supply', "
                 "'room AC', 'existing')"): {"2009": 108.46, "2010": 108.8}}},
            {"savings": {}, "total": {}},
            {"savings": {}, "total": {}}]
        cls.ok_tpmeas_fullchk_break_out = [{
            'AIA CZ1': {
                'Residential (New)': {
                    'Cooling (Equip.)': {"2009": 0.0375, "2010": 0.05625},
                    'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {},
                    'Heating (Equip.)': {"2009": 0.0125, "2010": 0.01875},
                    'Envelope': {}},
                'Residential (Existing)': {
                    'Cooling (Equip.)': {"2009": 0.3375, "2010": 0.31875},
                    'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {},
                    'Heating (Equip.)': {"2009": 0.1125, "2010": 0.10625},
                    'Envelope': {}},
                'Commercial (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}}},
            'AIA CZ2': {
                'Residential (New)': {
                    'Cooling (Equip.)': {"2009": 0.0375, "2010": 0.05625},
                    'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {},
                    'Heating (Equip.)': {"2009": 0.0125, "2010": 0.01875},
                    'Envelope': {}},
                'Residential (Existing)': {
                    'Cooling (Equip.)': {"2009": 0.3375, "2010": 0.31875},
                    'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {},
                    'Heating (Equip.)': {"2009": 0.1125, "2010": 0.10625},
                    'Envelope': {}},
                'Commercial (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}}},
            'AIA CZ3': {
                'Residential (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Residential (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}}},
            'AIA CZ4': {
                'Residential (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Residential (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}}},
            'AIA CZ5': {
                'Residential (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Residential (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}}}},
            {
            'AIA CZ1': {
                'Residential (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {},
                    'Water Heating': {"2009": 0.10, "2010": 0.15},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Residential (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {},
                    'Water Heating': {"2009": 0.90, "2010": 0.85},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}}},
            'AIA CZ2': {
                'Residential (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Residential (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}}},
            'AIA CZ3': {
                'Residential (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Residential (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}}},
            'AIA CZ4': {
                'Residential (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Residential (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}}},
            'AIA CZ5': {
                'Residential (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Residential (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}}}},
            {
            'AIA CZ1': {
                'Residential (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {"2009": 0.10, "2010": 0.15},
                    'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Residential (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {"2009": 0.90, "2010": 0.85},
                    'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}}},
            'AIA CZ2': {
                'Residential (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Residential (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}}},
            'AIA CZ3': {
                'Residential (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Residential (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}}},
            'AIA CZ4': {
                'Residential (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Residential (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}}},
            'AIA CZ5': {
                'Residential (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Residential (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (New)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}},
                'Commercial (Existing)': {
                    'Cooling (Equip.)': {}, 'Ventilation': {}, 'Lighting': {},
                    'Refrigeration': {}, 'Other': {}, 'Water Heating': {},
                    'Computers and Electronics': {}, 'Heating (Equip.)': {},
                    'Envelope': {}}}}]
        cls.ok_tpmeas_partchk_msegout = [{
            "stock": {
                "total": {
                    "all": {"2009": 148, "2010": 148},
                    "measure": {"2009": 148, "2010": 148}},
                "competed": {
                    "all": {"2009": 148, "2010": 148},
                    "measure": {"2009": 148, "2010": 148}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 766.677, "2010": 768.9562},
                    "efficient": {"2009": 647.8339, "2010": 649.7508}},
                "competed": {
                    "baseline": {"2009": 766.677, "2010": 768.9562},
                    "efficient": {"2009": 647.8339, "2010": 649.7508}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 43570.19, "2010": 43141.37},
                    "efficient": {"2009": 36815.4, "2010": 36449.93}},
                "competed": {
                    "baseline": {"2009": 43570.19, "2010": 43141.37},
                    "efficient": {"2009": 36815.4, "2010": 36449.93}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 2972, "2010": 2972},
                        "efficient": {"2009": 3700, "2010": 3700}},
                    "competed": {
                        "baseline": {"2009": 2972, "2010": 2972},
                        "efficient": {"2009": 3700, "2010": 3700}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 7819.26, "2010": 7479.78},
                        "efficient": {"2009": 6610.44, "2010": 6323.41}},
                    "competed": {
                        "baseline": {"2009": 7819.26, "2010": 7479.78},
                        "efficient": {"2009": 6610.44, "2010": 6323.41}}},
                "carbon": {
                    "total": {
                        "baseline": {
                            "2009": 1437816.14, "2010": 1423665.24},
                        "efficient": {
                            "2009": 1214908.11, "2010": 1202847.67}},
                    "competed": {
                        "baseline": {
                            "2009": 1437816.14, "2010": 1423665.24},
                        "efficient": {
                            "2009": 1214908.11, "2010": 1202847.67}}}},
            "lifetime": {"baseline": {"2009": 200.8108, "2010": 200.8108},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 1600000000, "2010": 2000000000},
                    "measure": {"2009": 1600000000, "2010": 2000000000}},
                "competed": {
                    "all": {"2009": 1600000000, "2010": 2000000000},
                    "measure": {"2009": 1600000000, "2010": 2000000000}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 12.76, "2010": 12.8},
                    "efficient": {"2009": 3.509, "2010": 3.52}},
                "competed": {
                    "baseline": {"2009": 12.76, "2010": 12.8},
                    "efficient": {"2009": 3.509, "2010": 3.52}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 725.3681, "2010": 718.9534},
                    "efficient": {"2009": 199.4762, "2010": 197.7122}},
                "competed": {
                    "baseline": {"2009": 725.3681, "2010": 718.9534},
                    "efficient": {"2009": 199.4762, "2010": 197.7122}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {
                            "2009": 20400000000, "2010": 24600000000},
                        "efficient": {
                            "2009": 16000000000, "2010": 20000000000}},
                    "competed": {
                        "baseline": {
                            "2009": 20400000000, "2010": 24600000000},
                        "efficient": {
                            "2009": 16000000000, "2010": 20000000000}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 129.3864, "2010": 123.776},
                        "efficient": {"2009": 35.58126, "2010": 34.0384}},
                    "competed": {
                        "baseline": {"2009": 129.3864, "2010": 123.776},
                        "efficient": {"2009": 35.58126, "2010": 34.0384}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 23937.15, "2010": 23725.46},
                        "efficient": {"2009": 6582.715, "2010": 6524.502}},
                    "competed": {
                        "baseline": {"2009": 23937.15, "2010": 23725.46},
                        "efficient": {"2009": 6582.715, "2010": 6524.502}}}},
            "lifetime": {"baseline": {"2009": 127.5, "2010": 123},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 600000000, "2010": 800000000},
                    "measure": {"2009": 600000000, "2010": 800000000}},
                "competed": {
                    "all": {"2009": 600000000, "2010": 800000000},
                    "measure": {"2009": 600000000, "2010": 800000000}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 6.38, "2010": 6.4},
                    "efficient": {"2009": 3.19, "2010": 3.2}},
                "competed": {
                    "baseline": {"2009": 6.38, "2010": 6.4},
                    "efficient": {"2009": 3.19, "2010": 3.2}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 362.684, "2010": 359.4767},
                    "efficient": {"2009": 181.342, "2010": 179.7383}},
                "competed": {
                    "baseline": {"2009": 362.684, "2010": 359.4767},
                    "efficient": {"2009": 181.342, "2010": 179.7383}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {
                            "2009": 900000000, "2010": 1200000000},
                        "efficient": {
                            "2009": 6000000000, "2010": 8000000000}},
                    "competed": {
                        "baseline": {
                            "2009": 900000000, "2010": 1200000000},
                        "efficient": {
                            "2009": 6000000000, "2010": 8000000000}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 64.6932, "2010": 61.888},
                        "efficient": {"2009": 32.3466, "2010": 30.944}},
                    "competed": {
                        "baseline": {"2009": 64.6932, "2010": 61.888},
                        "efficient": {"2009": 32.3466, "2010": 30.944}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 11968.57, "2010": 11862.73},
                        "efficient": {"2009": 5984.287, "2010": 5931.365}},
                    "competed": {
                        "baseline": {"2009": 11968.57, "2010": 11862.73},
                        "efficient": {"2009": 5984.287, "2010": 5931.365}}}},
            "lifetime": {"baseline": {"2009": 15, "2010": 15},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 600000000, "2010": 800000000},
                    "measure": {"2009": 600000000, "2010": 800000000}},
                "competed": {
                    "all": {"2009": 600000000, "2010": 800000000},
                    "measure": {"2009": 600000000, "2010": 800000000}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 146.74, "2010": 147.2},
                    "efficient": {"2009": 55.29333, "2010": 55.46667}},
                "competed": {
                    "baseline": {"2009": 146.74, "2010": 147.2},
                    "efficient": {"2009": 55.29333, "2010": 55.46667}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 8341.733, "2010": 8267.964},
                    "efficient": {"2009": 3143.262, "2010": 3115.465}},
                "competed": {
                    "baseline": {"2009": 8341.733, "2010": 8267.964},
                    "efficient": {"2009": 3143.262, "2010": 3115.465}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {
                            "2009": 3100000000, "2010": 4133333333.33},
                        "efficient": {
                            "2009": 6000000000, "2010": 8000000000}},
                    "competed": {
                        "baseline": {
                            "2009": 3100000000, "2010": 4133333333.33},
                        "efficient": {
                            "2009": 6000000000, "2010": 8000000000}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 1487.944, "2010": 1423.424},
                        "efficient": {"2009": 560.6744, "2010": 536.3627}},
                    "competed": {
                        "baseline": {"2009": 1487.944, "2010": 1423.424},
                        "efficient": {"2009": 560.6744, "2010": 536.3627}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 275277.18, "2010": 272842.8},
                        "efficient": {"2009": 103727.63, "2010": 102810.33}},
                    "competed": {
                        "baseline": {"2009": 275277.18, "2010": 272842.8},
                        "efficient": {"2009": 103727.63, "2010": 102810.33}}}},
            "lifetime": {"baseline": {"2009": 51.67, "2010": 51.67},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 600000000, "2010": 800000000},
                    "measure": {"2009": 600000000, "2010": 800000000}},
                "competed": {
                    "all": {"2009": 600000000, "2010": 800000000},
                    "measure": {"2009": 600000000, "2010": 800000000}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 146.74, "2010": 147.2},
                    "efficient": {"2009": 52.10333, "2010": 52.26667}},
                "competed": {
                    "baseline": {"2009": 146.74, "2010": 147.2},
                    "efficient": {"2009": 52.10333, "2010": 52.26667}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 8341.733, "2010": 8267.964},
                    "efficient": {"2009": 2961.92, "2010": 2935.726}},
                "competed": {
                    "baseline": {"2009": 8341.733, "2010": 8267.964},
                    "efficient": {"2009": 2961.92, "2010": 2935.726}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {
                            "2009": 3100000000, "2010": 4133333333.33},
                        "efficient": {
                            "2009": 6000000000, "2010": 8000000000}},
                    "competed": {
                        "baseline": {
                            "2009": 3100000000, "2010": 4133333333.33},
                        "efficient": {
                            "2009": 6000000000, "2010": 8000000000}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 1487.944, "2010": 1423.424},
                        "efficient": {"2009": 528.3278, "2010": 505.4187}},
                    "competed": {
                        "baseline": {"2009": 1487.944, "2010": 1423.424},
                        "efficient": {"2009": 528.3278, "2010": 505.4187}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 275277.18, "2010": 272842.8},
                        "efficient": {"2009": 97743.35, "2010": 96878.97}},
                    "competed": {
                        "baseline": {"2009": 275277.18, "2010": 272842.8},
                        "efficient": {"2009": 97743.35, "2010": 96878.97}}}},
            "lifetime": {"baseline": {"2009": 51.67, "2010": 51.67},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 11000000, "2010": 11000000},
                    "measure": {"2009": 11000000, "2010": 11000000}},
                "competed": {
                    "all": {"2009": 11000000, "2010": 11000000},
                    "measure": {"2009": 11000000, "2010": 11000000}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 31.9, "2010": 32.0},
                    "efficient": {"2009": 17.86, "2010": 17.92}},
                "competed": {
                    "baseline": {"2009": 31.9, "2010": 32.0},
                    "efficient": {"2009": 17.86, "2010": 17.92}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 1813.42, "2010": 1797.38},
                    "efficient": {"2009": 1015.52, "2010": 1006.53}},
                "competed": {
                    "baseline": {"2009": 1813.42, "2010": 1797.38},
                    "efficient": {"2009": 1015.52, "2010": 1006.53}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 154000000, "2010": 154000000},
                        "efficient": {"2009": 275000000, "2010": 275000000}},
                    "competed": {
                        "baseline": {"2009": 154000000, "2010": 154000000},
                        "efficient": {"2009": 275000000, "2010": 275000000}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 289.65, "2010": 273.6},
                        "efficient": {"2009": 162.21, "2010": 153.22}},
                    "competed": {
                        "baseline": {"2009": 289.65, "2010": 273.6},
                        "efficient": {"2009": 162.21, "2010": 153.22}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 59842.87, "2010": 59313.65},
                        "efficient": {"2009": 33512, "2010": 33215.65}},
                    "competed": {
                        "baseline": {"2009": 59842.87, "2010": 59313.65},
                        "efficient": {"2009": 33512, "2010": 33215.65}}}},
            "lifetime": {"baseline": {"2009": 140, "2010": 140},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 1.5, "2010": 2.25},
                    "measure": {"2009": 1.5, "2010": 2.25}},
                "competed": {
                    "all": {"2009": 1.5, "2010": 2.25},
                    "measure": {"2009": 1.5, "2010": 2.25}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 1.515, "2010": 2.2725},
                    "efficient": {"2009": 1.0908, "2010": 1.6362}},
                "competed": {
                    "baseline": {"2009": 1.515, "2010": 2.2725},
                    "efficient": {"2009": 1.0908, "2010": 1.6362}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 85.62139, "2010": 124.8003},
                    "efficient": {"2009": 61.6474, "2010": 89.85622}},
                "competed": {
                    "baseline": {"2009": 85.62139, "2010": 124.8003},
                    "efficient": {"2009": 61.6474, "2010": 89.85622}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 27, "2010": 40.5},
                        "efficient": {"2009": 37.5, "2010": 56.25}},
                    "competed": {
                        "baseline": {"2009": 27, "2010": 40.5},
                        "efficient": {"2009": 37.5, "2010": 56.25}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 17.0892, "2010": 24.49755},
                        "efficient": {"2009": 12.30422, "2010": 17.63823}},
                    "competed": {
                        "baseline": {"2009": 17.0892, "2010": 24.49755},
                        "efficient": {"2009": 12.30422, "2010": 17.63823}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 2825.506, "2010": 4118.409},
                        "efficient": {"2009": 2034.364, "2010": 2965.256}},
                    "competed": {
                        "baseline": {"2009": 2825.506, "2010": 4118.409},
                        "efficient": {"2009": 2034.364, "2010": 2965.256}}}},
            "lifetime": {"baseline": {"2009": 180, "2010": 180},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 13.5, "2010": 12.75},
                    "measure": {"2009": 13.5, "2010": 12.75}},
                "competed": {
                    "all": {"2009": 13.5, "2010": 12.75},
                    "measure": {"2009": 13.5, "2010": 12.75}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 13.635, "2010": 12.8775},
                    "efficient": {"2009": 9.8172, "2010": 9.2718}},
                "competed": {
                    "baseline": {"2009": 13.635, "2010": 12.8775},
                    "efficient": {"2009": 9.8172, "2010": 9.2718}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 770.5925, "2010": 707.2018},
                    "efficient": {"2009": 554.8266, "2010": 509.1853}},
                "competed": {
                    "baseline": {"2009": 770.5925, "2010": 707.2018},
                    "efficient": {"2009": 554.8266, "2010": 509.1853}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 243, "2010": 229.5},
                        "efficient": {"2009": 337.5, "2010": 318.75}},
                    "competed": {
                        "baseline": {"2009": 243, "2010": 229.5},
                        "efficient": {"2009": 337.5, "2010": 318.75}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 153.8028, "2010": 138.8195},
                        "efficient": {"2009": 110.738, "2010": 99.94998}},
                    "competed": {
                        "baseline": {"2009": 153.8028, "2010": 138.8195},
                        "efficient": {"2009": 110.738, "2010": 99.94998}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 25429.55, "2010": 23337.66},
                        "efficient": {"2009": 18309.28, "2010": 16803.11}},
                    "competed": {
                        "baseline": {"2009": 25429.55, "2010": 23337.66},
                        "efficient": {"2009": 18309.28, "2010": 16803.11}}}},
            "lifetime": {"baseline": {"2009": 180, "2010": 180},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 148, "2010": 148},
                    "measure": {"2009": 0, "2010": 148}},
                "competed": {
                    "all": {"2009": 18.17, "2010": 148},
                    "measure": {"2009": 0, "2010": 148}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 766.677, "2010": 768.9562},
                    "efficient": {"2009": 766.677, "2010": 649.7508}},
                "competed": {
                    "baseline": {"2009": 94.42735, "2010": 768.9562},
                    "efficient": {"2009": 94.42735, "2010": 649.7508}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 43570.19, "2010": 43141.37},
                    "efficient": {"2009": 43570.19, "2010": 36449.93}},
                "competed": {
                    "baseline": {"2009": 5366.289, "2010": 43141.37},
                    "efficient": {"2009": 5366.289, "2010": 36449.93}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 2972, "2010": 2972},
                        "efficient": {"2009": 2972, "2010": 3700}},
                    "competed": {
                        "baseline": {"2009": 364.016, "2010": 2972},
                        "efficient": {"2009": 364.016, "2010": 3700}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 7819.26, "2010": 7479.78},
                        "efficient": {"2009": 7819.26, "2010": 6323.41}},
                    "competed": {
                        "baseline": {"2009": 963.0867, "2010": 7479.78},
                        "efficient": {"2009": 963.0867, "2010": 6323.41}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 1437816.14, "2010": 1423665.24},
                        "efficient": {"2009": 1437816.14, "2010": 1202847.67}},
                    "competed": {
                        "baseline": {"2009": 177087.54, "2010": 1423665.24},
                        "efficient": {
                            "2009": 177087.54, "2010": 1202847.67}}}},
            "lifetime": {"baseline": {"2009": 200.81, "2010": 200.81},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 148, "2010": 148},
                    "measure": {"2009": 148, "2010": 0}},
                "competed": {
                    "all": {"2009": 148, "2010": 148},
                    "measure": {"2009": 148, "2010": 0}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 766.677, "2010": 768.9562},
                    "efficient": {"2009": 647.8339, "2010": 768.9562}},
                "competed": {
                    "baseline": {"2009": 766.677, "2010": 768.9562},
                    "efficient": {"2009": 647.8339, "2010": 768.9562}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 43570.19, "2010": 43141.37},
                    "efficient": {"2009": 36815.4, "2010": 43141.37}},
                "competed": {
                    "baseline": {"2009": 43570.19, "2010": 43141.37},
                    "efficient": {"2009": 36815.4, "2010": 43141.37}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 2972, "2010": 2972},
                        "efficient": {"2009": 3700, "2010": 2972}},
                    "competed": {
                        "baseline": {"2009": 2972, "2010": 2972},
                        "efficient": {"2009": 3700, "2010": 2972}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 7819.26, "2010": 7479.78},
                        "efficient": {"2009": 6610.44, "2010": 7479.78}},
                    "competed": {
                        "baseline": {"2009": 7819.26, "2010": 7479.78},
                        "efficient": {"2009": 6610.44, "2010": 7479.78}}},
                "carbon": {
                    "total": {
                        "baseline": {
                            "2009": 1437816.14, "2010": 1423665.24},
                        "efficient": {
                            "2009": 1214908.11, "2010": 1423665.24}},
                    "competed": {
                        "baseline": {
                            "2009": 1437816.14, "2010": 1423665.24},
                        "efficient": {
                            "2009": 1214908.11, "2010": 1423665.24}}}},
            "lifetime": {"baseline": {"2009": 200.8108, "2010": 200.8108},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 148, "2010": 148},
                    "measure": {"2009": 148, "2010": 148}},
                "competed": {
                    "all": {"2009": 148, "2010": 148},
                    "measure": {"2009": 148, "2010": 148}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 766.677, "2010": 768.9562},
                    "efficient": {"2009": 647.8339, "2010": 649.7508}},
                "competed": {
                    "baseline": {"2009": 766.677, "2010": 768.9562},
                    "efficient": {"2009": 647.8339, "2010": 649.7508}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 43570.19, "2010": 43141.37},
                    "efficient": {"2009": 36815.4, "2010": 36449.93}},
                "competed": {
                    "baseline": {"2009": 43570.19, "2010": 43141.37},
                    "efficient": {"2009": 36815.4, "2010": 36449.93}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 2972, "2010": 2972},
                        "efficient": {"2009": 3700, "2010": 3700}},
                    "competed": {
                        "baseline": {"2009": 2972, "2010": 2972},
                        "efficient": {"2009": 3700, "2010": 3700}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 7819.26, "2010": 7479.78},
                        "efficient": {"2009": 6610.44, "2010": 6323.41}},
                    "competed": {
                        "baseline": {"2009": 7819.26, "2010": 7479.78},
                        "efficient": {"2009": 6610.44, "2010": 6323.41}}},
                "carbon": {
                    "total": {
                        "baseline": {
                            "2009": 1437816.14, "2010": 1423665.24},
                        "efficient": {
                            "2009": 1214908.11, "2010": 1202847.67}},
                    "competed": {
                        "baseline": {
                            "2009": 1437816.14, "2010": 1423665.24},
                        "efficient": {
                            "2009": 1214908.11, "2010": 1202847.67}}}},
            "lifetime": {"baseline": {"2009": 200.8108, "2010": 200.8108},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 15, "2010": 15},
                    "measure": {"2009": 15, "2010": 15}},
                "competed": {
                    "all": {"2009": 15, "2010": 15},
                    "measure": {"2009": 15, "2010": 15}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 15.15, "2010": 15.15},
                    "efficient": {"2009": 34.452, "2010": 34.56}},
                "competed": {
                    "baseline": {"2009": 15.15, "2010": 15.15},
                    "efficient": {"2009": 34.452, "2010": 34.56}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 856.2139, "2010": 832.0021},
                    "efficient": {"2009": 1958.494, "2010": 1941.174}},
                "competed": {
                    "baseline": {"2009": 856.2139, "2010": 832.0021},
                    "efficient": {"2009": 1958.494, "2010": 1941.174}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 270, "2010": 270},
                        "efficient": {"2009": 375, "2010": 375}},
                    "competed": {
                        "baseline": {"2009": 270, "2010": 270},
                        "efficient": {"2009": 375, "2010": 375}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 170.892, "2010": 163.317},
                        "efficient": {"2009": 349.3433, "2010": 334.1952}},
                    "competed": {
                        "baseline": {"2009": 170.892, "2010": 163.317},
                        "efficient": {"2009": 349.3433, "2010": 334.1952}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 28255.06, "2010": 27456.07},
                        "efficient": {"2009": 64630.29, "2010": 64058.75}},
                    "competed": {
                        "baseline": {"2009": 28255.06, "2010": 27456.07},
                        "efficient": {"2009": 64630.29, "2010": 64058.75}}}},
            "lifetime": {"baseline": {"2009": 180, "2010": 180},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 11000000, "2010": 11000000},
                    "measure": {"2009": 11000000, "2010": 11000000}},
                "competed": {
                    "all": {"2009": 11000000, "2010": 11000000},
                    "measure": {"2009": 11000000, "2010": 11000000}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 31.9, "2010": 32.0},
                    "efficient": {"2009": 17.86, "2010": 17.92}},
                "competed": {
                    "baseline": {"2009": 31.9, "2010": 32.0},
                    "efficient": {"2009": 17.86, "2010": 17.92}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 1813.42, "2010": 1797.38},
                    "efficient": {"2009": 1015.52, "2010": 1006.53}},
                "competed": {
                    "baseline": {"2009": 1813.42, "2010": 1797.38},
                    "efficient": {"2009": 1015.52, "2010": 1006.53}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 154000000, "2010": 154000000},
                        "efficient": {"2009": 275000000, "2010": 275000000}},
                    "competed": {
                        "baseline": {"2009": 154000000, "2010": 154000000},
                        "efficient": {"2009": 275000000, "2010": 275000000}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 289.65, "2010": 273.6},
                        "efficient": {"2009": 162.21, "2010": 153.22}},
                    "competed": {
                        "baseline": {"2009": 289.65, "2010": 273.6},
                        "efficient": {"2009": 162.21, "2010": 153.22}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 59842.87, "2010": 59313.65},
                        "efficient": {"2009": 33512, "2010": 33215.65}},
                    "competed": {
                        "baseline": {"2009": 59842.87, "2010": 59313.65},
                        "efficient": {"2009": 33512, "2010": 33215.65}}}},
            "lifetime": {"baseline": {"2009": 140, "2010": 140},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 7.125, "2010": 6.9375},
                    "measure": {"2009": 7.125, "2010": 6.9375}},
                "competed": {
                    "all": {"2009": 7.125, "2010": 6.9375},
                    "measure": {"2009": 7.125, "2010": 6.9375}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 7.1963, "2010": 7.0069},
                    "efficient": {"2009": 5.1813, "2010": 5.0449}},
                "competed": {
                    "baseline": {"2009": 7.1963, "2010": 7.0069},
                    "efficient": {"2009": 5.1813, "2010": 5.0449}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 406.7016, "2010": 384.801},
                    "efficient": {"2009": 292.8251, "2010": 277.0567}},
                "competed": {
                    "baseline": {"2009": 406.7016, "2010": 384.801},
                    "efficient": {"2009": 292.8251, "2010": 277.0567}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 128.25, "2010": 124.875},
                        "efficient": {"2009": 178.125, "2010": 173.4375}},
                    "competed": {
                        "baseline": {"2009": 128.25, "2010": 124.875},
                        "efficient": {"2009": 178.125, "2010": 173.4375}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 81.1737, "2010": 75.53411},
                        "efficient": {"2009": 58.44506, "2010": 54.38456}},
                    "competed": {
                        "baseline": {"2009": 81.1737, "2010": 75.53411},
                        "efficient": {"2009": 58.44506, "2010": 54.38456}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 13421.15, "2010": 12698.43},
                        "efficient": {"2009": 9663.23, "2010": 9142.871}},
                    "competed": {
                        "baseline": {"2009": 13421.15, "2010": 12698.43},
                        "efficient": {"2009": 9663.23, "2010": 9142.871}}}},
            "lifetime": {"baseline": {"2009": 180, "2010": 180},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 70.3, "2010": 68.45},
                    "measure": {"2009": 70.3, "2010": 68.45}},
                "competed": {
                    "all": {"2009": 70.3, "2010": 68.45},
                    "measure": {"2009": 70.3, "2010": 68.45}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 364.1716, "2010": 355.6422},
                    "efficient": {"2009": 307.7211, "2010": 300.5098}},
                "competed": {
                    "baseline": {"2009": 364.1716, "2010": 355.6422},
                    "efficient": {"2009": 307.7211, "2010": 300.5098}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 20695.84, "2010": 19952.88},
                    "efficient": {"2009": 17487.31, "2010": 16858.09}},
                "competed": {
                    "baseline": {"2009": 20695.84, "2010": 19952.88},
                    "efficient": {"2009": 17487.31, "2010": 16858.09}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 1411.7, "2010": 1374.55},
                        "efficient": {"2009": 1757.5, "2010": 1711.25}},
                    "competed": {
                        "baseline": {"2009": 1411.7, "2010": 1374.55},
                        "efficient": {"2009": 1757.5, "2010": 1711.25}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 3714.15, "2010": 3459.40},
                        "efficient": {"2009": 3139.96, "2010": 2924.58}},
                    "competed": {
                        "baseline": {"2009": 3714.15, "2010": 3459.40},
                        "efficient": {"2009": 3139.96, "2010": 2924.58}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 682962.67, "2010": 658445.18},
                        "efficient": {"2009": 577081.35, "2010": 556317.05}},
                    "competed": {
                        "baseline": {"2009": 682962.67, "2010": 658445.18},
                        "efficient": {"2009": 577081.35, "2010": 556317.05}}}},
            "lifetime": {"baseline": {"2009": 200.81, "2010": 200.81},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 11000000, "2010": 11000000},
                    "measure": {"2009": 11000000, "2010": 11000000}},
                "competed": {
                    "all": {"2009": 11000000, "2010": 11000000},
                    "measure": {"2009": 11000000, "2010": 11000000}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 114.84, "2010": 115.2},
                    "efficient": {"2009": 86.13, "2010": 86.4}},
                "competed": {
                    "baseline": {"2009": 114.84, "2010": 115.2},
                    "efficient": {"2009": 86.13, "2010": 86.4}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 6528.313, "2010": 6470.58},
                    "efficient": {"2009": 4896.234, "2010": 4852.935}},
                "competed": {
                    "baseline": {"2009": 6528.313, "2010": 6470.58},
                    "efficient": {"2009": 4896.234, "2010": 4852.935}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 0, "2010": 0},
                        "efficient": {"2009": 275000000, "2010": 275000000}},
                    "competed": {
                        "baseline": {"2009": 0, "2010": 0},
                        "efficient": {"2009": 275000000, "2010": 275000000}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 1042.747, "2010": 984.96},
                        "efficient": {"2009": 782.0604, "2010": 738.72}},
                    "competed": {
                        "baseline": {"2009": 1042.747, "2010": 984.96},
                        "efficient": {"2009": 782.0604, "2010": 738.72}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 215434.31, "2010": 213529.15},
                        "efficient": {"2009": 161575.74, "2010": 160146.86}},
                    "competed": {
                        "baseline": {"2009": 215434.31, "2010": 213529.15},
                        "efficient": {"2009": 161575.74, "2010": 160146.86}}}},
            "lifetime": {"baseline": {"2009": 10, "2010": 10},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 729, "2010": 729},
                    "measure": {"2009": 729, "2010": 729}},
                "competed": {
                    "all": {"2009": 729, "2010": 729},
                    "measure": {"2009": 729, "2010": 729}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 1177.11, "2010": 1180.8},
                    "efficient": {"2009": 588.555, "2010": 590.4}},
                "competed": {
                    "baseline": {"2009": 1177.11, "2010": 1180.8},
                    "efficient": {"2009": 588.555, "2010": 590.4}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 66915.2, "2010": 66323.45},
                    "efficient": {"2009": 33457.6, "2010": 33161.72}},
                "competed": {
                    "baseline": {"2009": 66915.2, "2010": 66323.45},
                    "efficient": {"2009": 33457.6, "2010": 33161.72}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 0, "2010": 0},
                        "efficient": {"2009": 18225, "2010": 18225}},
                    "competed": {
                        "baseline": {"2009": 0, "2010": 0},
                        "efficient": {"2009": 18225, "2010": 18225}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 11935.9, "2010": 11418.34},
                        "efficient": {"2009": 5967.948, "2010": 5709.168}},
                    "competed": {
                        "baseline": {"2009": 11935.9, "2010": 11418.34},
                        "efficient": {"2009": 5967.948, "2010": 5709.168}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 2208201.73, "2010": 2188673.79},
                        "efficient": {"2009": 1104100.86, "2010": 1094336.90}},
                    "competed": {
                        "baseline": {"2009": 2208201.73, "2010": 2188673.79},
                        "efficient": {"2009": 1104100.86, "2010": 1094336.90}}}
                        },
            "lifetime": {"baseline": {"2009": 10, "2010": 10},
                         "measure": 1}}]
        cls.ok_mapmas_partchck_msegout = [{
            "stock": {
                "total": {
                    "all": {"2009": 11000000, "2010": 11000000},
                    "measure": {"2009": 298571.43, "2010": 597142.86}},
                "competed": {
                    "all": {"2009": 298571.43, "2010": 597142.86},
                    "measure": {"2009": 298571.43, "2010": 597142.86}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 31.90, "2010": 32.00},
                    "efficient": {"2009": 31.52, "2010": 31.24}},
                "competed": {
                    "baseline": {"2009": 0.87, "2010": 1.74},
                    "efficient": {"2009": 0.48, "2010": 0.97}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 1813.42, "2010": 1797.38},
                    "efficient": {"2009": 1791.76, "2010": 1754.45}},
                "competed": {
                    "baseline": {"2009": 49.22, "2010": 97.57},
                    "efficient": {"2009": 27.56, "2010": 54.64}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 154000000, "2010": 154000000},
                        "efficient": {
                            "2009": 157284285.71, "2010": 160568571.42857143}},
                    "competed": {
                        "baseline": {"2009": 4180000, "2010": 8360000},
                        "efficient": {
                            "2009": 7464285.71, "2010": 14928571.43}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 289.65, "2010": 273.60},
                        "efficient": {"2009": 286.19, "2010": 267.06}},
                    "competed": {
                        "baseline": {"2009": 7.86, "2010": 14.85},
                        "efficient": {"2009": 4.40, "2010": 8.32}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 59842.87, "2010": 59313.65},
                        "efficient": {"2009": 59128.17, "2010": 57896.90}},
                    "competed": {
                        "baseline": {"2009": 1624.31, "2010": 3219.88},
                        "efficient": {"2009": 909.61, "2010": 1803.14}}}},
            "lifetime": {"baseline": {"2009": 140, "2010": 140},
                         "measure": 1}}]
        cls.ok_distmeas_out = [
            [120.86, 100, 1741.32, 100, 1.0, 1],
            [11.9, 100, 374.73, 100, 0.93, 100],
            [55.44, 100, 6426946929.70, 100, 1.0, 1]]
        cls.ok_partialmeas_out = [{
            "stock": {
                "total": {
                    "all": {"2009": 18, "2010": 18},
                    "measure": {"2009": 18, "2010": 18}},
                "competed": {
                    "all": {"2009": 18, "2010": 18},
                    "measure": {"2009": 18, "2010": 18}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 57.42, "2010": 57.6},
                    "efficient": {"2009": 27.5616, "2010": 27.648}},
                "competed": {
                    "baseline": {"2009": 57.42, "2010": 57.6},
                    "efficient": {"2009": 27.5616, "2010": 27.648}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 3264.156, "2010": 3235.29},
                    "efficient": {"2009": 1566.795, "2010": 1552.939}},
                "competed": {
                    "baseline": {"2009": 3264.156, "2010": 3235.29},
                    "efficient": {"2009": 1566.795, "2010": 1552.939}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 216, "2010": 216},
                        "efficient": {"2009": 450, "2010": 450}},
                    "competed": {
                        "baseline": {"2009": 216, "2010": 216},
                        "efficient": {"2009": 450, "2010": 450}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 582.2388, "2010": 556.992},
                        "efficient": {"2009": 279.4746, "2010": 267.3562}},
                    "competed": {
                        "baseline": {"2009": 582.2388, "2010": 556.992},
                        "efficient": {"2009": 279.4746, "2010": 267.3562}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 107717.16, "2010": 106764.58},
                        "efficient": {"2009": 51704.24, "2010": 51247}},
                    "competed": {
                        "baseline": {"2009": 107717.16, "2010": 106764.58},
                        "efficient": {"2009": 51704.24, "2010": 51247}}}},
            "lifetime": {"baseline": {"2009": 120, "2010": 120},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 52, "2010": 52},
                    "measure": {"2009": 52, "2010": 52}},
                "competed": {
                    "all": {"2009": 52, "2010": 52},
                    "measure": {"2009": 52, "2010": 52}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 165.88, "2010": 166.4},
                    "efficient": {"2009": 67.1176, "2010": 67.328}},
                "competed": {
                    "baseline": {"2009": 165.88, "2010": 166.4},
                    "efficient": {"2009": 67.1176, "2010": 67.328}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 9429.785, "2010": 9346.394},
                    "efficient": {"2009": 3815.436, "2010": 3781.695}},
                "competed": {
                    "baseline": {"2009": 9429.785, "2010": 9346.394},
                    "efficient": {"2009": 3815.436, "2010": 3781.695}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 526, "2010": 526},
                        "efficient": {"2009": 1300, "2010": 1300}},
                    "competed": {
                        "baseline": {"2009": 526, "2010": 526},
                        "efficient": {"2009": 1300, "2010": 1300}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 1682.023, "2010": 1609.088},
                        "efficient": {"2009": 680.5725, "2010": 651.0618}},
                    "competed": {
                        "baseline": {"2009": 1682.023, "2010": 1609.088},
                        "efficient": {"2009": 680.5725, "2010": 651.0618}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 311182.9, "2010": 308431},
                        "efficient": {"2009": 125909.39, "2010": 124795.93}},
                    "competed": {
                        "baseline": {"2009": 311182.9, "2010": 308431},
                        "efficient": {"2009": 125909.39, "2010": 124795.93}}}},
            "lifetime": {"baseline": {"2009": 101.1538, "2010": 101.1538},
                         "measure": 1}}]
        cls.ok_warnmeas_out = [
            [("WARNING: 'warn measure 1' has invalid "
              "sub-market scaling fraction source title, author, "
              "organization, and/or year information"),
             ("WARNING: 'warn measure 1' has invalid "
              "sub-market scaling fraction source URL information"),
             ("WARNING: 'warn measure 1' has invalid "
              "sub-market scaling fraction derivation information"),
             ("WARNING (CRITICAL): 'warn measure 1' has "
              "insufficient sub-market source information and "
              "will be removed from analysis")],
            [("WARNING: 'warn measure 2' has invalid "
              "sub-market scaling fraction source URL information"),
             ("WARNING: 'warn measure 2' has invalid "
              "sub-market scaling fraction derivation information"),
             ("WARNING (CRITICAL): 'warn measure 2' has "
              "insufficient sub-market source information and "
              "will be removed from analysis")],
            [("WARNING: 'warn measure 3' has invalid "
              "sub-market scaling fraction source title, author, "
              "organization, and/or year information")]]

    def test_mseg_ok_full_tp(self):
        """Test 'fill_mkts' function given valid inputs.

        Notes:
            Checks the all branches of measure 'markets' attribute
            under a Technical potential scenario.

        Raises:
            AssertionError: If function yields unexpected results.
        """
        # Run function on all measure objects and check output
        for idx, measure in enumerate(self.ok_tpmeas_fullchk_in):
            measure.fill_mkts(self.sample_mseg_in, self.sample_cpl_in,
                              self.convert_data, self.tsv_data, self.verbose)
            # Restrict the full check of all branches of 'markets' to only
            # the first three measures in this set. For the remaining two
            # measures, only check the competed choice parameter outputs.
            # These last two measures are intended to test a special case where
            # measure cost units are in $/ft^2 floor rather than $/unit and
            # competed choice parameters must be scaled accordingly
            if idx < 3:
                self.dict_check(
                    measure.markets['Technical potential']['master_mseg'],
                    self.ok_tpmeas_fullchk_msegout[idx])
                self.dict_check(
                    measure.markets['Technical potential']['mseg_adjust'][
                        'secondary mseg adjustments'],
                    self.ok_tpmeas_fullchk_msegadjout[idx])
                self.dict_check(
                    measure.markets['Technical potential']['mseg_out_break'],
                    self.ok_tpmeas_fullchk_break_out[idx])
            self.dict_check(
                measure.markets['Technical potential']['mseg_adjust'][
                    'competed choice parameters'],
                self.ok_tpmeas_fullchk_competechoiceout[idx])

    def test_mseg_ok_part_tp(self):
        """Test 'fill_mkts' function given valid inputs.

        Notes:
            Checks the 'master_mseg' branch of measure 'markets' attribute
            under a Technical potential scenario.

        Raises:
            AssertionError: If function yields unexpected results.
        """
        for idx, measure in enumerate(self.ok_tpmeas_partchk_in):
            measure.fill_mkts(self.sample_mseg_in, self.sample_cpl_in,
                              self.convert_data, self.tsv_data, self.verbose)
            self.dict_check(
                measure.markets['Technical potential']['master_mseg'],
                self.ok_tpmeas_partchk_msegout[idx])

    def test_mseg_ok_part_map(self):
        """Test 'fill_mkts' function given valid inputs.

        Notes:
            Checks the 'master_mseg' branch of measure 'markets' attribute
            under a Max adoption potential scenario.

        Raises:
            AssertionError: If function yields unexpected results.
        """
        # Run function on all measure objects and check for correct
        # output
        for idx, measure in enumerate(self.ok_mapmeas_partchk_in):
            measure.fill_mkts(self.sample_mseg_in, self.sample_cpl_in,
                              self.convert_data, self.tsv_data, self.verbose)
            self.dict_check(
                measure.markets['Max adoption potential']['master_mseg'],
                self.ok_mapmas_partchck_msegout[idx])

    def test_mseg_ok_distrib(self):
        """Test 'fill_mkts' function given valid inputs.

        Notes:
            Valid input measures are assigned distributions on
            their cost, performance, and/or lifetime attributes.

        Raises:
            AssertionError: If function yields unexpected results.
        """
        # Seed random number generator to yield repeatable results
        numpy.random.seed(1234)
        for idx, measure in enumerate(self.ok_distmeas_in):
            # Generate lists of energy and cost output values
            measure.fill_mkts(
                self.sample_mseg_in, self.sample_cpl_in,
                self.convert_data, self.tsv_data, self.verbose)
            test_outputs = measure.markets[
                'Technical potential']['master_mseg']
            test_e = test_outputs["energy"]["total"]["efficient"]["2009"]
            test_c = test_outputs[
                "cost"]["stock"]["total"]["efficient"]["2009"]
            test_l = test_outputs["lifetime"]["measure"]
            if type(test_l) == float:
                test_l = [test_l]
            # Calculate mean values from output lists for testing
            param_e = round(sum(test_e) / len(test_e), 2)
            param_c = round(sum(test_c) / len(test_c), 2)
            param_l = round(sum(test_l) / len(test_l), 2)
            # Check mean values and length of output lists to ensure
            # correct
            self.assertEqual([
                param_e, len(test_e), param_c, len(test_c),
                param_l, len(test_l)], self.ok_distmeas_out[idx])

    def test_mseg_partial(self):
        """Test 'fill_mkts' function given partially valid inputs.

        Raises:
            AssertionError: If function yields unexpected results.
        """
        # Run function on all measure objects and check output
        for idx, measure in enumerate(self.ok_partialmeas_in):
            measure.fill_mkts(self.sample_mseg_in, self.sample_cpl_in,
                              self.convert_data, self.tsv_data, self.verbose)
            self.dict_check(
                measure.markets['Technical potential']['master_mseg'],
                self.ok_partialmeas_out[idx])

    def test_mseg_fail_inputs(self):
        """Test 'fill_mkts' function given invalid inputs.

        Raises:
            AssertionError: If ValueError is not raised.
        """
        # Run function on all measure objects and check output
        for idx, measure in enumerate(self.failmeas_inputs_in):
            with self.assertRaises(ValueError):
                measure.fill_mkts(self.sample_mseg_in, self.sample_cpl_in,
                                  self.convert_data, self.tsv_data,
                                  self.verbose)

    def test_mseg_fail_missing(self):
        """Test 'fill_mkts' function given a measure with missing baseline data.

        Raises:
            AssertionError: If KeyError is not raised.
        """
        # Run function on all measure objects and check output
        with self.assertRaises(KeyError):
            self.failmeas_missing_in.fill_mkts(
                self.sample_mseg_in, self.sample_cpl_in,
                self.convert_data, self.tsv_data, self.verbose)

    def test_mseg_warn(self):
        """Test 'fill_mkts' function given incomplete inputs.

        Raises:
            AssertionError: If function yields unexpected results or
            UserWarning is not raised.
        """
        # Run function on all measure objects and check output
        for idx, mw in enumerate(self.warnmeas_in):
            # Assert that inputs generate correct warnings and that measure
            # is marked inactive where necessary
            with warnings.catch_warnings(record=True) as w:
                mw.fill_mkts(self.sample_mseg_in, self.sample_cpl_in,
                             self.convert_data, self.tsv_data, self.verbose)
                # Check correct number of warnings is yielded
                self.assertEqual(len(w), len(self.ok_warnmeas_out[idx]))
                # Check correct type of warnings is yielded
                self.assertTrue(all([
                    issubclass(wn.category, UserWarning) for wn in w]))
                [self.assertTrue(wm in str([wmt.message for wmt in w])) for
                    wm in self.ok_warnmeas_out[idx]]
                # Check that measure is marked inactive when a critical
                # warning message is yielded
                if any(['CRITICAL' in x for x in self.ok_warnmeas_out[
                        idx]]):
                    self.assertTrue(mw.remove is True)
                else:
                    self.assertTrue(mw.remove is False)


class TimeSensitiveValuationTest(unittest.TestCase, CommonMethods):
    """Test the operation of the 'gen_tsv_facts' and 'apply_tsv' functions.

    Ensure that the first function properly generates a set of factors used
    to reweight energy, cost, and carbon data to reflect time sensitive
    valuation of energy efficiency, and that the second, supporting function
    properly modifies baseline energy load shapes to reflect the impacts of
    a time-sensitive energy efficiency measure.

    Attributes:
      sample_tsv_data (dict): Sample time-varying load, price, and emissions.
      sample_bldg_sect (string): Sample baseline microsegment building sector.
      sample_base_load (list): Sample base load shape to modify.
      ok_tsv_measures_in (list): Sample time sensitive efficiency measures.
      sample_rel_perf (list): Sample relative performance for each measure.
      ok_eff_load_out (list): Sample efficient load shape outcomes.
      ok_tsv_facts_out (list): Sample reweighting factor outcomes.

    """

    @classmethod
    def setUpClass(cls):
        """Define variables and objects for use across all class functions."""

        # Base directory
        base_dir = os.getcwd()
        handyvars = ecm_prep.UsefulVars(base_dir,
                                        ecm_prep.UsefulInputFiles())
        # Hard code aeo_years to fit test years
        handyvars.aeo_years = ["2009", "2010"]
        cls.sample_mskeys = (
          "primary", "AIA_CZ1", "single family home", "electricity",
          "heating", "supply", "ASHP", "new")
        cls.sample_bldg_sect = "residential"
        cls.sample_tsv_data = {
          "load": {
            "AIA_CZ1": {
              "residential": {
                "heating": {
                  "winter": {
                    "months": [
                      1,
                      2,
                      12
                    ],
                    "annual_days": 90,
                    "fractions": {
                      "weekday": [
                        0.012202256455352733,
                        0.012202256455352733,
                        0.012790369837445772,
                        0.01354335327206579,
                        0.014412162613847488,
                        0.015259279121150411,
                        0.015853297848280774,
                        0.015928471021456836,
                        0.015332968218593672,
                        0.014155976960109057,
                        0.012669478965647952,
                        0.011162898928851443,
                        0.009864588218574728,
                        0.008928691840308131,
                        0.008419616601380887,
                        0.008337276785137526,
                        0.008657777623759138,
                        0.009295666950390356,
                        0.010056738183651286,
                        0.010714075913172366,
                        0.011132857599974094,
                        0.01131327739593043,
                        0.011359135633914552,
                        0.011432694001907577
                      ],
                      "weekend": [
                        0.005241914064820976,
                        0.005241914064820976,
                        0.005479964558914669,
                        0.005766692417852683,
                        0.006121364449071813,
                        0.006531657677672043,
                        0.006924303274533763,
                        0.007151601035392774,
                        0.007047308555582134,
                        0.006554883454248733,
                        0.005797373314887126,
                        0.004993297019974449,
                        0.004324320580840767,
                        0.003874842240940412,
                        0.003646836954407323,
                        0.0036070550958290726,
                        0.0037213635750740865,
                        0.00395311415662022,
                        0.0042500266143626715,
                        0.004552908776331854,
                        0.004815668602839308,
                        0.005012872039222633,
                        0.00513509652610582,
                        0.005182074671008964
                      ]
                    }
                  },
                  "intermediate": {
                    "months": [
                      10,
                      11,
                      3,
                      4
                    ],
                    "annual_days": 122,
                    "fractions": {
                      "weekday": [
                        0.016540836528367037,
                        0.016540836528367037,
                        0.017338056890759825,
                        0.018358767768800296,
                        0.01953648709877104,
                        0.020684800586448338,
                        0.02149002597211394,
                        0.02159192738464149,
                        0.02078469025187142,
                        0.01918921321259228,
                        0.017174182597878333,
                        0.015131929659109733,
                        0.013371997362956857,
                        0.012103337827973246,
                        0.011413258059649647,
                        0.011301641864297534,
                        0.01173609855665128,
                        0.012600792977195817,
                        0.01363246731561619,
                        0.014523525126744765,
                        0.015091206968853771,
                        0.015335776025594586,
                        0.01539793941486195,
                        0.015497651869252492
                      ],
                      "weekend": [
                        0.007105705732312879,
                        0.007105705732312879,
                        0.0074283964020843305,
                        0.007817071944200307,
                        0.008297849586519569,
                        0.008854024851955437,
                        0.009386277772145768,
                        0.00969439251464354,
                        0.00955301826423356,
                        0.008885508682426062,
                        0.00785866160462477,
                        0.0067686915159653645,
                        0.005861856787361929,
                        0.005252563926608114,
                        0.0049434900937521484,
                        0.004889563574346076,
                        0.0050445150684337615,
                        0.005358665856751855,
                        0.005761147188358289,
                        0.006171720785694292,
                        0.006527906328293286,
                        0.006795226542057347,
                        0.006960908624276779,
                        0.007024590109589927
                      ]
                    }
                  },
                  "summer": {
                    "months": [
                      5,
                      6,
                      7,
                      8,
                      9
                    ],
                    "annual_days": 153,
                    "fractions": {
                      "weekday": [
                        0.0010590636426289091,
                        0.0010590636426289091,
                        0.001094523946095479,
                        0.0011479534348979225,
                        0.0012135479343554246,
                        0.0012775786485038569,
                        0.001316407844730775,
                        0.0013019566152529193,
                        0.0012199040244830553,
                        0.0010880214351182012,
                        0.0009479778372020717,
                        0.0008349335540973944,
                        0.0007598879766524797,
                        0.0007167523336559638,
                        0.0006985608004971985,
                        0.0007058953734481931,
                        0.0007411524747124881,
                        0.0007972762496801779,
                        0.0008575041127562266,
                        0.0009071925861580299,
                        0.0009419989359581119,
                        0.0009663272187837232,
                        0.0009884582999645222,
                        0.0010172826848597876
                      ],
                      "weekend": [
                        0.0004817841819163308,
                        0.0004817841819163308,
                        0.0005027855713473914,
                        0.0005286093783583508,
                        0.0005565142687933293,
                        0.0005841833554293074,
                        0.0006075787234184459,
                        0.000618502357523313,
                        0.0006058653602035742,
                        0.0005638157685378343,
                        0.00049960965014296,
                        0.00043034690944955496,
                        0.00037199075437145007,
                        0.000332194578928617,
                        0.0003108630908884448,
                        0.00030421774349246824,
                        0.00030762615314860656,
                        0.00031711380102401697,
                        0.00033072136392778284,
                        0.0003482878625037381,
                        0.00036938031048864233,
                        0.0003915214454442425,
                        0.00040977858976023237,
                        0.0004171754859352801
                      ]
                    }
                  }
                }
              }
            }
          },
          "price": {
            "AIA_CZ1": {
              "residential": {
                "winter": {
                  "months": [
                    1,
                    2,
                    12
                  ],
                  "annual_days": 90.25,
                  "rates": {
                    "weekday": [
                      0.6562552797163391,
                      0.6562552797163391,
                      0.6562552797163391,
                      0.6562552797163391,
                      0.6562722224680656,
                      0.6578442485863384,
                      0.7235267658386892,
                      0.8409053866455017,
                      1.012563919002179,
                      1.217271077418888,
                      1.2125005556734563,
                      1.2057496380698587,
                      1.1988043072105958,
                      1.1826547505128486,
                      1.1833338836255691,
                      1.1835511313538214,
                      1.2407170480621692,
                      1.2770113386833148,
                      1.2766376843522398,
                      1.2525419733224212,
                      0.997037561299839,
                      0.7503122897528398,
                      0.6824694705086938,
                      0.6728076562529395
                    ],
                    "weekend": [
                      0.6644122978887247,
                      0.6644122978887247,
                      0.6644122978887247,
                      0.6644122978887247,
                      0.6644122978887247,
                      0.665113732663588,
                      0.6738333378241788,
                      0.6976045234405559,
                      0.7073939270906661,
                      0.7071505858599368,
                      0.7065294988071219,
                      0.7063849706660476,
                      0.6894592001856883,
                      0.681247569162237,
                      0.6813266103046596,
                      0.6816697006818776,
                      0.7058360518456535,
                      0.7092645790001153,
                      0.7092918676319172,
                      0.7100055253846985,
                      0.7083692085692868,
                      0.699741815510325,
                      0.6763846942735929,
                      0.6743807072224638
                    ]
                  }
                },
                "intermediate": {
                  "months": [
                    10,
                    11,
                    3,
                    4
                  ],
                  "annual_days": 122,
                  "rates": {
                    "weekday": [
                      0.6562778441085866,
                      0.6562778441085866,
                      0.6562778441085866,
                      0.6562778441085866,
                      0.656279641853995,
                      0.6578447685953613,
                      0.705174669017633,
                      0.8286455185797903,
                      0.9995293595504565,
                      1.2047023639699554,
                      1.2127149443241592,
                      1.2059862624248205,
                      1.1996754637517355,
                      1.183527727165945,
                      1.184196410698559,
                      1.1851517809866334,
                      1.2638951596822328,
                      1.2879865402334234,
                      1.2872477149518382,
                      1.2566187789076564,
                      0.9871707759014134,
                      0.749295816267223,
                      0.6823792035508683,
                      0.6728309763973485
                    ],
                    "weekend": [
                      0.6644478260228615,
                      0.6644478260228615,
                      0.6644478260228615,
                      0.6644478260228615,
                      0.6644478260228615,
                      0.6651398435784992,
                      0.6737605831198047,
                      0.6854959315714353,
                      0.7008227999148096,
                      0.7005426165885539,
                      0.6999493829042236,
                      0.6997976349876648,
                      0.6894625284116876,
                      0.6812703115779266,
                      0.6814184511586658,
                      0.6817205786085438,
                      0.7059317555796673,
                      0.7092665306112451,
                      0.709274613329601,
                      0.7099917167610817,
                      0.7084051532773447,
                      0.699783289154462,
                      0.6763460541022601,
                      0.6744115729038507
                    ]
                  }
                },
                "summer": {
                  "months": [
                    5,
                    6,
                    7,
                    8,
                    9
                  ],
                  "annual_days": 153,
                  "rates": {
                    "weekday": [
                      0.6458245873740424,
                      0.6458245873740424,
                      0.6458245873740424,
                      0.6458245873740424,
                      0.6458245873740424,
                      0.6468994741735525,
                      0.6721704283419366,
                      0.7877528153346143,
                      0.9508403698379019,
                      1.218453626925188,
                      1.270531964130501,
                      1.2733827123523953,
                      1.4115085817189656,
                      1.4987952877758426,
                      1.5191561886103309,
                      1.5199249270082422,
                      1.6247504057906499,
                      1.6339418703545154,
                      1.6025160033698258,
                      1.3678843705031805,
                      1.0303149049834759,
                      0.7475568270923396,
                      0.6723258865801299,
                      0.6636779143465007
                    ],
                    "weekend": [
                      0.6534945611557802,
                      0.6534945611557802,
                      0.6534945611557802,
                      0.6534945611557802,
                      0.6534945611557802,
                      0.6542221029139391,
                      0.6621663178269653,
                      0.6796723657035797,
                      0.6892275843534218,
                      0.6890302919287634,
                      0.688594812154047,
                      0.6885055018323561,
                      0.6764007903284276,
                      0.6677141658845643,
                      0.6678930377629508,
                      0.6683674190022503,
                      0.6876227199936777,
                      0.6910965171473628,
                      0.6911239469667035,
                      0.690723663696209,
                      0.6872672314327727,
                      0.6849410388318566,
                      0.6645116515218538,
                      0.6634792797131637
                    ]
                  }
                }
              }
            }
          },
          "emissions": {
            "AIA_CZ1": {
              "winter": {
                "months": [
                  1,
                  2,
                  12
                ],
                "annual_days": 90.25,
                "factors": [
                  1.0808327943771008,
                  1.0947294879594474,
                  1.0909604832627986,
                  0.997259933763779,
                  1.0157987104859902,
                  1.0160614041206557,
                  1.0477835926945642,
                  1.000430414155741,
                  1.023557292451596,
                  0.960032661017396,
                  0.917036500578013,
                  0.9705004448862705,
                  0.9907681555516679,
                  1.0253381814057205,
                  0.9844841561876502,
                  0.9042117573723634,
                  1.0284123659853506,
                  1.0036148259369406,
                  0.9833833200372775,
                  0.952786486602425,
                  0.9137505041285251,
                  0.9183607987573171,
                  1.0297440696206162,
                  1.0501616586607956
                ]
              },
              "intermediate": {
                "months": [
                  9,
                  10,
                  11,
                  3,
                  4
                ],
                "annual_days": 152,
                "factors": [
                  1.0658956503894756,
                  1.0727670538462724,
                  1.0631207028580707,
                  1.046332293005439,
                  1.015708019925993,
                  1.026753672777928,
                  1.021262021827931,
                  0.9949980406706456,
                  0.9757903062587946,
                  0.9396316891528453,
                  0.9466447200833301,
                  0.9476982359938386,
                  0.9727191746106075,
                  0.9655198479731756,
                  0.9631011731360967,
                  0.9523456404643373,
                  1.008536357395883,
                  1.0106262570856785,
                  1.020217337466093,
                  0.995225325404544,
                  0.9852466168013723,
                  0.9828527161667133,
                  0.9910882940666929,
                  1.035918852638241
                ]
              },
              "summer": {
                "months": [
                  5,
                  6,
                  7,
                  8
                ],
                "annual_days": 123,
                "factors": [
                  1.1435710315058578,
                  1.1855937369569567,
                  1.1841115412910492,
                  1.1711267994327952,
                  1.138416978159702,
                  1.0879526698838258,
                  1.047850567207246,
                  0.9915300582880294,
                  0.9257377330283679,
                  0.9323171624462354,
                  0.9230809453005281,
                  0.9171957664527647,
                  0.9220163795107141,
                  0.9322139542622108,
                  0.9698324615055369,
                  0.9801952991546521,
                  0.9454291136003109,
                  0.9252177083898578,
                  0.9350063389981491,
                  0.941638621913107,
                  0.8621879023886238,
                  0.8691889278276335,
                  0.9908346745164235,
                  1.077753627979422
                ]
              }
            }
          }
        }
        cls.sample_base_load = cls.sample_tsv_data[
          "load"]["AIA_CZ1"]["residential"]["heating"]["winter"][
          "fractions"]["weekday"]
        sample_tsv_measures_in = [
          {"name": "sample conventional efficiency",
           "energy_efficiency": 0.2,
           "energy_efficiency_units": "relative savings (constant)",
           "markets": None,
           "installed_cost": 25,
           "cost_units": "2014$/unit",
           "market_entry_year": None,
           "market_exit_year": None,
           "product_lifetime": 1,
           "market_scaling_fractions": None,
           "market_scaling_fractions_source": None,
           "measure_type": "full service",
           "structure_type": ["new", "existing"],
           "bldg_type": "single family home",
           "climate_zone": "AIA_CZ1",
           "fuel_type": "electricity",
           "fuel_switch_to": None,
           "end_use": "heating",
           "technology": ["resistance heat", "ASHP"],
           "time_sensitive_valuation": {
              "conventional": {
                "start": 6, "stop": 10}
           }},
          {"name": "sample peak shaving",
           "energy_efficiency": 0,
           "energy_efficiency_units": "relative savings (constant)",
           "markets": None,
           "installed_cost": 25,
           "cost_units": "2014$/unit",
           "market_entry_year": None,
           "market_exit_year": None,
           "product_lifetime": 1,
           "market_scaling_fractions": None,
           "market_scaling_fractions_source": None,
           "measure_type": "full service",
           "structure_type": ["new", "existing"],
           "bldg_type": "single family home",
           "climate_zone": "AIA_CZ1",
           "fuel_type": "electricity",
           "fuel_switch_to": None,
           "end_use": "heating",
           "technology": ["resistance heat", "ASHP"],
           "time_sensitive_valuation": {
              "shave": {
                "start": 6, "stop": 10, "peak_fraction": 0.9}
           }},
          {"name": "sample valley filling",
           "energy_efficiency": 0,
           "energy_efficiency_units": "relative savings (constant)",
           "markets": None,
           "installed_cost": 25,
           "cost_units": "2014$/unit",
           "market_entry_year": None,
           "market_exit_year": None,
           "product_lifetime": 1,
           "market_scaling_fractions": None,
           "market_scaling_fractions_source": None,
           "measure_type": "full service",
           "structure_type": ["new", "existing"],
           "bldg_type": "single family home",
           "climate_zone": "AIA_CZ1",
           "fuel_type": "electricity",
           "fuel_switch_to": None,
           "end_use": "heating",
           "technology": ["resistance heat", "ASHP"],
           "time_sensitive_valuation": {
              "fill": {
                "start": 11, "stop": 5, "peak_fraction": 0.7}
           }},
          {"name": "sample shifting 1",
           "energy_efficiency": 0.2,
           "energy_efficiency_units": "relative savings (constant)",
           "markets": None,
           "installed_cost": 25,
           "cost_units": "2014$/unit",
           "market_entry_year": None,
           "market_exit_year": None,
           "product_lifetime": 1,
           "market_scaling_fractions": None,
           "market_scaling_fractions_source": None,
           "measure_type": "full service",
           "structure_type": ["new", "existing"],
           "bldg_type": "single family home",
           "climate_zone": "AIA_CZ1",
           "fuel_type": "electricity",
           "fuel_switch_to": None,
           "end_use": "heating",
           "technology": ["resistance heat", "ASHP"],
           "time_sensitive_valuation": {
              "shift": {
                "start": 6, "stop": 10, "offset_hrs_earlier": 10}
           }},
          {"name": "sample shifting 2",
           "energy_efficiency": 0,
           "energy_efficiency_units": "relative savings (constant)",
           "markets": None,
           "installed_cost": 25,
           "cost_units": "2014$/unit",
           "market_entry_year": None,
           "market_exit_year": None,
           "product_lifetime": 1,
           "market_scaling_fractions": None,
           "market_scaling_fractions_source": None,
           "measure_type": "full service",
           "structure_type": ["new", "existing"],
           "bldg_type": "single family home",
           "climate_zone": "AIA_CZ1",
           "fuel_type": "electricity",
           "fuel_switch_to": None,
           "end_use": "heating",
           "technology": ["resistance heat", "ASHP"],
           "time_sensitive_valuation": {
              "shift": {
                "start": None, "stop": None, "offset_hrs_earlier": 10}
           }},
          {"name": "sample shifting 3",
           "energy_efficiency": 0.2,
           "energy_efficiency_units": "relative savings (constant)",
           "markets": None,
           "installed_cost": 25,
           "cost_units": "2014$/unit",
           "market_entry_year": None,
           "market_exit_year": None,
           "product_lifetime": 1,
           "market_scaling_fractions": None,
           "market_scaling_fractions_source": None,
           "measure_type": "full service",
           "structure_type": ["new", "existing"],
           "bldg_type": "single family home",
           "climate_zone": "AIA_CZ1",
           "fuel_type": "electricity",
           "fuel_switch_to": None,
           "end_use": "heating",
           "technology": ["resistance heat", "ASHP"],
           "time_sensitive_valuation": {
              "shift": {
                "start": 10, "stop": 20, "offset_hrs_earlier": 10}
           }},
          {"name": "sample reshaping 1",
           "energy_efficiency": 0,
           "energy_efficiency_units": "relative savings (constant)",
           "markets": None,
           "installed_cost": 25,
           "cost_units": "2014$/unit",
           "market_entry_year": None,
           "market_exit_year": None,
           "product_lifetime": 1,
           "market_scaling_fractions": None,
           "market_scaling_fractions_source": None,
           "measure_type": "full service",
           "structure_type": ["new", "existing"],
           "bldg_type": "single family home",
           "climate_zone": "AIA_CZ1",
           "fuel_type": "electricity",
           "fuel_switch_to": None,
           "end_use": "heating",
           "technology": ["resistance heat", "ASHP"],
           "time_sensitive_valuation": {
              "shape": {
                "start": 1, "stop": 24, "flatten_fraction": 0.5}
           }},
          {"name": "sample reshaping 2",
           "energy_efficiency": 0,
           "energy_efficiency_units": "relative savings (constant)",
           "markets": None,
           "installed_cost": 25,
           "cost_units": "2014$/unit",
           "market_entry_year": None,
           "market_exit_year": None,
           "product_lifetime": 1,
           "market_scaling_fractions": None,
           "market_scaling_fractions_source": None,
           "measure_type": "full service",
           "structure_type": ["new", "existing"],
           "bldg_type": "single family home",
           "climate_zone": "AIA_CZ1",
           "fuel_type": "electricity",
           "fuel_switch_to": None,
           "end_use": "heating",
           "technology": ["resistance heat", "ASHP"],
           "time_sensitive_valuation": {
              "shape": {
                "custom": [
                  0.795398312, 0.700814216, 0.619305406, 0.56054921,
                  0.528589128, 0.523419779, 0.543541035, 0.583588151,
                  0.631368709, 0.672636809, 0.698928201, 0.710255076,
                  0.713134087, 0.71775213, 0.766065772, 0.766065772,
                  0.802987921, 0.850260722, 0.90480515, 0.957987688,
                  0.995280578, 1, 0.962613938, 0.888721644]}
           }},
          {"name": "sample shift, and shape",
           "energy_efficiency": 0.2,
           "energy_efficiency_units": "relative savings (constant)",
           "markets": None,
           "installed_cost": 25,
           "cost_units": "2014$/unit",
           "market_entry_year": None,
           "market_exit_year": None,
           "product_lifetime": 1,
           "market_scaling_fractions": None,
           "market_scaling_fractions_source": None,
           "measure_type": "full service",
           "structure_type": ["new", "existing"],
           "bldg_type": "single family home",
           "climate_zone": "AIA_CZ1",
           "fuel_type": "electricity",
           "fuel_switch_to": None,
           "end_use": "heating",
           "technology": ["resistance heat", "ASHP"],
           "time_sensitive_valuation": {
            "shift": {
              "start": 6, "stop": 10, "offset_hrs_earlier": 10},
            "shape": {
              "start": 1, "stop": 24, "flatten_fraction": 0.5}
            }
           }]
        cls.ok_tsv_measures_in = [ecm_prep.Measure(
          handyvars, **x) for x in sample_tsv_measures_in]
        cls.sample_rel_perf = [
          {yr: (1 - m.energy_efficiency) for yr in handyvars.aeo_years}
          for m in cls.ok_tsv_measures_in]
        cls.ok_eff_load_out = [
          {"2009": [0.015252821, 0.015252821, 0.015987962, 0.016929192,
                    0.018015203, 0.015259279, 0.015853298, 0.015928471,
                    0.015332968, 0.014155977, 0.015836849, 0.013953624,
                    0.012330735, 0.011160865, 0.010524521, 0.010421596,
                    0.010822222, 0.011619584, 0.012570923, 0.013392595,
                    0.013916072, 0.014141597, 0.01419892, 0.014290868],
           "2010": [0.015252821, 0.015252821, 0.015987962, 0.016929192,
                    0.018015203, 0.015259279, 0.015853298, 0.015928471,
                    0.015332968, 0.014155977, 0.015836849, 0.013953624,
                    0.012330735, 0.011160865, 0.010524521, 0.010421596,
                    0.010822222, 0.011619584, 0.012570923, 0.013392595,
                    0.013916072, 0.014141597, 0.01419892, 0.014290868]},
          {"2009": [0.012202256, 0.012202256, 0.01279037, 0.013543353,
                    0.014412163, 0.014335624, 0.014335624, 0.014335624,
                    0.014335624, 0.014155977, 0.012669479, 0.011162899,
                    0.009864588, 0.008928692, 0.008419617, 0.008337277,
                    0.008657778, 0.009295667, 0.010056738, 0.010714076,
                    0.011132858, 0.011313277, 0.011359136, 0.011432694],
           "2010": [0.012202256, 0.012202256, 0.01279037, 0.013543353,
                    0.014412163, 0.014335624, 0.014335624, 0.014335624,
                    0.014335624, 0.014155977, 0.012669479, 0.011162899,
                    0.009864588, 0.008928692, 0.008419617, 0.008337277,
                    0.008657778, 0.009295667, 0.010056738, 0.010714076,
                    0.011132858, 0.011313277, 0.011359136, 0.011432694]},
          {"2009": [0.012202256, 0.012202256, 0.01279037, 0.013543353,
                    0.014412163, 0.015259279, 0.015853298, 0.015928471,
                    0.015332968, 0.014155977, 0.012669479, 0.011162899,
                    0.01114993, 0.01114993, 0.01114993, 0.01114993,
                    0.01114993, 0.01114993, 0.01114993, 0.01114993,
                    0.01114993, 0.011313277, 0.011359136, 0.011432694],
           "2010": [0.012202256, 0.012202256, 0.01279037, 0.013543353,
                    0.014412163, 0.015259279, 0.015853298, 0.015928471,
                    0.015332968, 0.014155977, 0.012669479, 0.011162899,
                    0.01114993, 0.01114993, 0.01114993, 0.01114993,
                    0.01114993, 0.01114993, 0.01114993, 0.01114993,
                    0.01114993, 0.011313277, 0.011359136, 0.011432694]},
          {"2009": [0.015252821, 0.015252821, 0.015987962, 0.016929192,
                    0.018015203, 0.015259279, 0.015853298, 0.015928471,
                    0.015332968, 0.014155977, 0.015836849, 0.013953624,
                    0.012330735, 0.011160865, 0.010524521, 0.010421596,
                    0.010822222, 0.011619584, 0.012570923, 0.017219095,
                    0.017742572, 0.017968096, 0.018025419, 0.018117367],
           "2010": [0.015252821, 0.015252821, 0.015987962, 0.016929192,
                    0.018015203, 0.015259279, 0.015853298, 0.015928471,
                    0.015332968, 0.014155977, 0.015836849, 0.013953624,
                    0.012330735, 0.011160865, 0.010524521, 0.010421596,
                    0.010822222, 0.011619584, 0.012570923, 0.017219095,
                    0.017742572, 0.017968096, 0.018025419, 0.018117367]},
          {"2009": [0.012669479, 0.011162899, 0.009864588, 0.008928692,
                    0.008419617, 0.008337277, 0.008657778, 0.009295667,
                    0.010056738, 0.010714076, 0.011132858, 0.011313277,
                    0.011359136, 0.011432694, 0.012202256, 0.012202256,
                    0.01279037, 0.013543353, 0.014412163, 0.015259279,
                    0.015853298, 0.015928471, 0.015332968, 0.014155977],
           "2010": [0.012669479, 0.011162899, 0.009864588, 0.008928692,
                    0.008419617, 0.008337277, 0.008657778, 0.009295667,
                    0.010056738, 0.010714076, 0.011132858, 0.011313277,
                    0.011359136, 0.011432694, 0.012202256, 0.012202256,
                    0.01279037, 0.013543353, 0.014412163, 0.015259279,
                    0.015853298, 0.015928471, 0.015332968, 0.014155977]},
          {"2009": [0.017804248, 0.017804248, 0.018539389, 0.019480619,
                    0.02056663, 0.021625526, 0.022368049, 0.022462016,
                    0.021717637, 0.016707404, 0.012669479, 0.011162899,
                    0.009864588, 0.008928692, 0.008419617, 0.008337277,
                    0.008657778, 0.009295667, 0.010056738, 0.010714076,
                    0.013916072, 0.014141597, 0.01419892, 0.016842294],
           "2010": [0.017804248, 0.017804248, 0.018539389, 0.019480619,
                    0.02056663, 0.021625526, 0.022368049, 0.022462016,
                    0.021717637, 0.016707404, 0.012669479, 0.011162899,
                    0.009864588, 0.008928692, 0.008419617, 0.008337277,
                    0.008657778, 0.009295667, 0.010056738, 0.010714076,
                    0.013916072, 0.014141597, 0.01419892, 0.016842294]},
          {"2009": [0.012039153, 0.012039153, 0.012333209, 0.012709701,
                    0.013144106, 0.013567664, 0.013864673, 0.01390226,
                    0.013604508, 0.013016013, 0.012272764, 0.011519474,
                    0.010870318, 0.01040237, 0.010147833, 0.010106663,
                    0.010266913, 0.010585858, 0.010966393, 0.011295062,
                    0.011504453, 0.011594663, 0.011617592, 0.011654371],
           "2010": [0.012039153, 0.012039153, 0.012333209, 0.012709701,
                    0.013144106, 0.013567664, 0.013864673, 0.01390226,
                    0.013604508, 0.013016013, 0.012272764, 0.011519474,
                    0.010870318, 0.01040237, 0.010147833, 0.010106663,
                    0.010266913, 0.010585858, 0.010966393, 0.011295062,
                    0.011504453, 0.011594663, 0.011617592, 0.011654371]},
          {"2009": [0.012669479, 0.011162899, 0.009864588, 0.008928692,
                    0.008419617, 0.008337277, 0.008657778, 0.009295667,
                    0.010056738, 0.010714076, 0.011132858, 0.011313277,
                    0.011359136, 0.011432694, 0.012202256, 0.012202256,
                    0.01279037, 0.013543353, 0.014412163, 0.015259279,
                    0.015853298, 0.015928471, 0.015332968, 0.014155977],
           "2010": [0.012669479, 0.011162899, 0.009864588, 0.008928692,
                    0.008419617, 0.008337277, 0.008657778, 0.009295667,
                    0.010056738, 0.010714076, 0.011132858, 0.011313277,
                    0.011359136, 0.011432694, 0.012202256, 0.012202256,
                    0.01279037, 0.013543353, 0.014412163, 0.015259279,
                    0.015853298, 0.015928471, 0.015332968, 0.014155977]},
          {"2009": [0.015048941, 0.015048941, 0.015416512, 0.015887126,
                    0.016430132, 0.01505217, 0.015349179, 0.015386766,
                    0.015089014, 0.014500519, 0.015340955, 0.014399342,
                    0.013587898, 0.013002963, 0.012684791, 0.012633328,
                    0.012833641, 0.013232322, 0.013707992, 0.016032078,
                    0.016293816, 0.016406579, 0.01643524, 0.016481214],
           "2010": [0.015048941, 0.015048941, 0.015416512, 0.015887126,
                    0.016430132, 0.01505217, 0.015349179, 0.015386766,
                    0.015089014, 0.014500519, 0.015340955, 0.014399342,
                    0.013587898, 0.013002963, 0.012684791, 0.012633328,
                    0.012833641, 0.013232322, 0.013707992, 0.016032078,
                    0.016293816, 0.016406579, 0.01643524, 0.016481214]}]
        cls.ok_tsv_facts_out = [[{
            "energy": {
                "efficient": {
                  "2009": 1.18249064, "2010": 1.18249064}
                },
            "cost": {
                "baseline": 0.857055123,
                "efficient": {
                  "2009": 1.016109525, "2010": 1.016109525}
            },
            "carbon": {
                "baseline": 1.002314946,
                "efficient": {
                  "2009": 1.185384091, "2010": 1.185384091}
            }}, {"2009": 0.8, "2010": 0.8}], [{
             "energy": {
                "efficient": {
                  "2009": 0.984918266, "2010": 0.984918266}
                },
             "cost": {
                "baseline": 0.857055123,
                "efficient": {
                  "2009": 0.845306061, "2010": 0.845306061}},
             "carbon": {
                "baseline": 1.002314946,
                "efficient": {
                  "2009": 0.987089849, "2010": 0.987089849}}},
            {"2009": 1, "2010": 1}]]

    def test_load_modification(self):
        """Test the 'apply_tsv' function given valid inputs."""
        for idx, measure in enumerate(self.ok_tsv_measures_in):
            eff_load_out = measure.apply_tsv(
              self.sample_base_load, self.sample_mskeys,
              self.sample_rel_perf[idx])
            self.dict_check(eff_load_out, self.ok_eff_load_out[idx])

    def test_frac_gen(self):
        """Test the 'gen_tsv_facts' function given valid inputs."""
        for idx, measure in enumerate(self.ok_tsv_measures_in[0:2]):
            tsv_facts_out = self.ok_tsv_measures_in[idx].gen_tsv_facts(
              self.sample_tsv_data, self.sample_mskeys, self.sample_bldg_sect,
              self.sample_rel_perf[idx])
            # Check first output from 'gen_tsv_facts' function
            self.dict_check(tsv_facts_out[0], self.ok_tsv_facts_out[idx][0])
            # Check second output from 'gen_tsv_facts' function
            self.dict_check(tsv_facts_out[1], self.ok_tsv_facts_out[idx][1])


class PartitionMicrosegmentTest(unittest.TestCase, CommonMethods):
    """Test the operation of the 'partition_microsegment' function.

    Ensure that the function properly partitions an input microsegment
    to yield the required total, competed, and efficient stock, energy,
    carbon and cost information.

    Attributes:
        time_horizons (list): A series of modeling time horizons to use
            in the various test functions of the class.
        handyvars (object): Global variables to use for the test measure.
        sample_measure_in (dict): Sample measure attributes.
        ok_diffuse_params_in (NoneType): Placeholder for eventual technology
            diffusion parameters to be used in 'adjusted adoption' scenario.
        ok_mskeys_in (list): Sample key chains associated with the market
            microsegment being partitioned by the function.
        ok_mkt_scale_frac_in (float): Sample market microsegment scaling
            factor.
        ok_tsv_scale_fracs_in (dict): Sample time sensitive valuation scaling
            fractions.
        ok_newbldg_frac_in (list): Sample fraction of the total stock that
            is new construction, by year.
        ok_stock_in (list): Sample baseline microsegment stock data, by year.
        ok_energy_in (list): Sample baseline microsegment energy data, by year.
        ok_carb_in (list): Sample baseline microsegment carbon data, by year.
        ok_base_cost_in (list): Sample baseline technology unit costs, by year.
        ok_cost_meas_in (list): Sample measure unit costs.
        ok_cost_energy_base_in (numpy.ndarray): Sample baseline fuel costs.
        ok_cost_energy_meas_in (numpy.ndarray): Sample measure fuel costs.
        ok_relperf_in (list): Sample measure relative performance values.
        ok_life_base_in (dict): Sample baseline technology lifetimes, by year.
        ok_life_meas_in (int): Sample measure lifetime.
        ok_ssconv_base_in (numpy.ndarray): Sample baseline fuel site-source
            conversions, by year.
        ok_ssconv_meas_in (numpy.ndarray): Sample measure fuel site-source
            conversions, by year.
        ok_carbint_base_in (numpy.ndarray): Sample baseline fuel carbon
            intensities, by year.
        ok_carbint_meas_in (numpy.ndarray): Sample measure fuel carbon
            intensities, by year.
        ok_out (list): Outputs that should be yielded by the function given
            valid inputs.
    """

    @classmethod
    def setUpClass(cls):
        """Define variables and objects for use across all class functions."""
        cls.time_horizons = [
            ["2009", "2010", "2011"], ["2025", "2026", "2027"],
            ["2020", "2021", "2022"]]
        # Base directory
        base_dir = os.getcwd()
        cls.handyvars = ecm_prep.UsefulVars(base_dir,
                                            ecm_prep.UsefulInputFiles())
        cls.handyvars.retro_rate = 0.02
        cls.handyvars.ccosts = numpy.array(
            (b'Test', 1, 4, 1, 1, 1, 1, 1, 1, 3), dtype=[
                ('Category', 'S11'), ('2009', '<f8'),
                ('2010', '<f8'), ('2011', '<f8'),
                ('2020', '<f8'), ('2021', '<f8'),
                ('2022', '<f8'), ('2025', '<f8'),
                ('2026', '<f8'), ('2027', '<f8')])
        sample_measure_in = {
            "name": "sample measure 1",
            "active": 1,
            "market_entry_year": None,
            "market_exit_year": None,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "bldg_type": ["single family home"],
            "fuel_type": {
                "primary": ["electricity"],
                "secondary": None},
            "fuel_switch_to": None,
            "end_use": {
                "primary": ["heating", "cooling"],
                "secondary": None},
            "technology": {
                "primary": ["resistance heat", "ASHP", "GSHP", "room AC"],
                "secondary": None}}
        cls.measure_instance = ecm_prep.Measure(
            cls.handyvars, **sample_measure_in)
        cls.ok_diffuse_params_in = None
        cls.ok_mskeys_in = [
            ('primary', 'AIA_CZ1', 'single family home',
             'electricity', 'heating', 'supply', 'resistance heat',
             'new'),
            ('primary', 'AIA_CZ1', 'single family home',
             'electricity', 'heating', 'supply', 'resistance heat',
             'existing')]
        cls.ok_mkt_scale_frac_in = 1
        cls.ok_new_bldg_constr = [{
            "annual new": {"2009": 10, "2010": 5, "2011": 10},
            "total new": {"2009": 10, "2010": 15, "2011": 25}},
            {
            "annual new": {"2025": 10, "2026": 5, "2027": 10},
            "total new": {"2025": 10, "2026": 15, "2027": 25}},
            {
            "annual new": {"2020": 10, "2021": 95, "2022": 10},
            "total new": {"2020": 10, "2021": 100, "2022": 100}}]
        cls.ok_stock_in = [
            {"2009": 100, "2010": 200, "2011": 300},
            {"2025": 400, "2026": 500, "2027": 600},
            {"2020": 700, "2021": 800, "2022": 900}]
        cls.ok_energy_scnd_in = [
            {"2009": 10, "2010": 20, "2011": 30},
            {"2025": 40, "2026": 50, "2027": 60},
            {"2020": 70, "2021": 80, "2022": 90}]
        cls.ok_energy_in = [
            {"2009": 10, "2010": 20, "2011": 30},
            {"2025": 40, "2026": 50, "2027": 60},
            {"2020": 70, "2021": 80, "2022": 90}]
        cls.ok_carb_in = [
            {"2009": 30, "2010": 60, "2011": 90},
            {"2025": 120, "2026": 150, "2027": 180},
            {"2020": 210, "2021": 240, "2022": 270}]
        cls.ok_base_cost_in = [
            {"2009": 10, "2010": 10, "2011": 10},
            {"2025": 20, "2026": 20, "2027": 20},
            {"2020": 30, "2021": 30, "2022": 30}]
        cls.ok_cost_meas_in = [20, 30, 40]
        cls.ok_cost_energy_base_in, cls.ok_cost_energy_meas_in = \
            (numpy.array((b'Test', 1, 2, 2, 2, 2, 2, 2, 2, 2),
                         dtype=[('Category', 'S11'), ('2009', '<f8'),
                                ('2010', '<f8'), ('2011', '<f8'),
                                ('2020', '<f8'), ('2021', '<f8'),
                                ('2022', '<f8'), ('2025', '<f8'),
                                ('2026', '<f8'), ('2027', '<f8')])
             for n in range(2))
        cls.ok_relperf_in = [
            {"2009": 0.30, "2010": 0.30, "2011": 0.30},
            {"2025": 0.15, "2026": 0.15, "2027": 0.15},
            {"2020": 0.75, "2021": 0.75, "2022": 0.75}]
        cls.ok_life_base_in = {
            "2009": 10, "2010": 10, "2011": 10,
            "2020": 10, "2021": 10, "2022": 10,
            "2025": 10, "2026": 10, "2027": 10}
        cls.ok_life_meas_in = 10
        cls.ok_ssconv_base_in, cls.ok_ssconv_meas_in = \
            (numpy.array((b'Test', 1, 1, 1, 1, 1, 1, 1, 1, 1),
                         dtype=[('Category', 'S11'), ('2009', '<f8'),
                                ('2010', '<f8'), ('2011', '<f8'),
                                ('2020', '<f8'), ('2021', '<f8'),
                                ('2022', '<f8'), ('2025', '<f8'),
                                ('2026', '<f8'), ('2027', '<f8')])
             for n in range(2))
        cls.ok_carbint_base_in, cls.ok_carbint_meas_in = \
            (numpy.array((b'Test', 1, 1, 1, 1, 1, 1, 1, 1, 1),
                         dtype=[('Category', 'S11'), ('2009', '<f8'),
                                ('2010', '<f8'), ('2011', '<f8'),
                                ('2020', '<f8'), ('2021', '<f8'),
                                ('2022', '<f8'), ('2025', '<f8'),
                                ('2026', '<f8'), ('2027', '<f8')])
             for n in range(2))
        cls.ok_out = [
            [[[
                {"2009": 100, "2010": 200, "2011": 300},
                {"2009": 10, "2010": 20, "2011": 30},
                {"2009": 30, "2010": 60, "2011": 90},
                {"2009": 100, "2010": 200, "2011": 300},
                {"2009": 3, "2010": 6, "2011": 9},
                {"2009": 9, "2010": 18, "2011": 27},
                {"2009": 100, "2010": 66.67, "2011": 120},
                {"2009": 10, "2010": 6.67, "2011": 12},
                {"2009": 30, "2010": 20, "2011": 36},
                {"2009": 100, "2010": 66.67, "2011": 120},
                {"2009": 3, "2010": 2, "2011": 3.6},
                {"2009": 9, "2010": 6, "2011": 10.8},
                {"2009": 1000, "2010": 2000, "2011": 3000},
                {"2009": 10, "2010": 40, "2011": 60},
                {"2009": 30, "2010": 240, "2011": 90},
                {"2009": 2000, "2010": 4000, "2011": 6000},
                {"2009": 3, "2010": 12, "2011": 18},
                {"2009": 9, "2010": 72, "2011": 27},
                {"2009": 1000, "2010": 666.67, "2011": 1200},
                {"2009": 10, "2010": 13.33, "2011": 24},
                {"2009": 30, "2010": 80, "2011": 36},
                {"2009": 2000, "2010": 1333.33, "2011": 2400},
                {"2009": 3, "2010": 4, "2011": 7.2},
                {"2009": 9, "2010": 24, "2011": 10.8}],
                [
                {"2009": 100, "2010": 200, "2011": 300},
                {"2009": 10, "2010": 20, "2011": 30},
                {"2009": 30, "2010": 60, "2011": 90},
                {"2009": 100, "2010": 200, "2011": 300},
                {"2009": 3, "2010": 6, "2011": 9},
                {"2009": 9, "2010": 18, "2011": 27},
                {"2009": 100, "2010": 0, "2011": 0},
                {"2009": 10, "2010": 0, "2011": 0},
                {"2009": 30, "2010": 0, "2011": 0},
                {"2009": 100, "2010": 0, "2011": 0},
                {"2009": 3, "2010": 0, "2011": 0},
                {"2009": 9, "2010": 0, "2011": 0},
                {"2009": 1000, "2010": 2000, "2011": 3000},
                {"2009": 10, "2010": 40, "2011": 60},
                {"2009": 30, "2010": 240, "2011": 90},
                {"2009": 2000, "2010": 4000, "2011": 6000},
                {"2009": 3, "2010": 12, "2011": 18},
                {"2009": 9, "2010": 72, "2011": 27},
                {"2009": 1000, "2010": 0, "2011": 0},
                {"2009": 10, "2010": 0, "2011": 0},
                {"2009": 30, "2010": 0, "2011": 0},
                {"2009": 2000, "2010": 0, "2011": 0},
                {"2009": 3, "2010": 0, "2011": 0},
                {"2009": 9, "2010": 0, "2011": 0}]],
             [[
                 {"2009": 100, "2010": 200, "2011": 300},
                 {"2009": 10, "2010": 20, "2011": 30},
                 {"2009": 30, "2010": 60, "2011": 90},
                 {"2009": 100, "2010": 166.67, "2011": 286.67},
                 {"2009": 3, "2010": 6, "2011": 9},
                 {"2009": 9, "2010": 18, "2011": 27},
                 {"2009": 100, "2010": 66.67, "2011": 120},
                 {"2009": 10, "2010": 6.67, "2011": 12},
                 {"2009": 30, "2010": 20, "2011": 36},
                 {"2009": 100, "2010": 66.67, "2011": 120},
                 {"2009": 3, "2010": 2, "2011": 3.6},
                 {"2009": 9, "2010": 6, "2011": 10.8},
                 {"2009": 1000, "2010": 2000, "2011": 3000},
                 {"2009": 10, "2010": 40, "2011": 60},
                 {"2009": 30, "2010": 240, "2011": 90},
                 {"2009": 2000, "2010": 3666.67, "2011": 5866.67},
                 {"2009": 3, "2010": 12, "2011": 18},
                 {"2009": 9, "2010": 72, "2011": 27},
                 {"2009": 1000, "2010": 666.67, "2011": 1200},
                 {"2009": 10, "2010": 13.33, "2011": 24},
                 {"2009": 30, "2010": 80, "2011": 36},
                 {"2009": 2000, "2010": 1333.33, "2011": 2400},
                 {"2009": 3, "2010": 4, "2011": 7.2},
                 {"2009": 9, "2010": 24, "2011": 10.8}],
                 [
                 {"2009": 100, "2010": 200, "2011": 300},
                 {"2009": 10, "2010": 20, "2011": 30},
                 {"2009": 30, "2010": 60, "2011": 90},
                 {"2009": 12, "2010": 48, "2011": 108},
                 {"2009": 9.16, "2010": 16.84, "2011": 23.0448},
                 {"2009": 27.48, "2010": 50.52, "2011": 69.1344},
                 {"2009": 12, "2010": 24, "2011": 36},
                 {"2009": 1.2, "2010": 2.4, "2011": 3.6},
                 {"2009": 3.6, "2010": 7.2, "2011": 10.8},
                 {"2009": 12, "2010": 24, "2011": 36},
                 {"2009": 0.36, "2010": 0.72, "2011": 1.08},
                 {"2009": 1.08, "2010": 2.16, "2011": 3.24},
                 {"2009": 1000, "2010": 2000, "2011": 3000},
                 {"2009": 10, "2010": 40, "2011": 60},
                 {"2009": 30, "2010": 240, "2011": 90},
                 {"2009": 1120, "2010": 2480, "2011": 4080},
                 {"2009": 9.16, "2010": 33.68, "2011": 46.0896},
                 {"2009": 27.48, "2010": 202.10, "2011": 69.1344},
                 {"2009": 120, "2010": 240, "2011": 360},
                 {"2009": 1.2, "2010": 4.8, "2011": 7.2},
                 {"2009": 3.6, "2010": 28.8, "2011": 10.8},
                 {"2009": 240, "2010": 480, "2011": 720},
                 {"2009": 0.36, "2010": 1.44, "2011": 2.16},
                 {"2009": 1.08, "2010": 8.64, "2011": 3.24}]]],
            [[[
                {"2025": 400, "2026": 500, "2027": 600},
                {"2025": 40, "2026": 50, "2027": 60},
                {"2025": 120, "2026": 150, "2027": 180},
                {"2025": 400, "2026": 500, "2027": 600},
                {"2025": 6, "2026": 7.5, "2027": 9},
                {"2025": 18, "2026": 22.5, "2027": 27},
                {"2025": 400, "2026": 166.67, "2027": 240},
                {"2025": 40, "2026": 16.67, "2027": 24},
                {"2025": 120, "2026": 50, "2027": 72},
                {"2025": 400, "2026": 166.67, "2027": 240},
                {"2025": 6, "2026": 2.5, "2027": 3.6},
                {"2025": 18, "2026": 7.5, "2027": 10.8},
                {"2025": 8000, "2026": 10000, "2027": 12000},
                {"2025": 80, "2026": 100, "2027": 120},
                {"2025": 120, "2026": 150, "2027": 540},
                {"2025": 12000, "2026": 15000, "2027": 18000},
                {"2025": 12, "2026": 15, "2027": 18},
                {"2025": 18, "2026": 22.5, "2027": 81},
                {"2025": 8000, "2026": 3333.33, "2027": 4800},
                {"2025": 80, "2026": 33.33, "2027": 48},
                {"2025": 120, "2026": 50, "2027": 216},
                {"2025": 12000, "2026": 5000, "2027": 7200},
                {"2025": 12, "2026": 5, "2027": 7.2},
                {"2025": 18, "2026": 7.5, "2027": 32.4}],
                [
                {"2025": 400, "2026": 500, "2027": 600},
                {"2025": 40, "2026": 50, "2027": 60},
                {"2025": 120, "2026": 150, "2027": 180},
                {"2025": 400, "2026": 500, "2027": 600},
                {"2025": 6, "2026": 7.5, "2027": 9},
                {"2025": 18, "2026": 22.5, "2027": 27},
                {"2025": 400, "2026": 0, "2027": 0},
                {"2025": 40, "2026": 0, "2027": 0},
                {"2025": 120, "2026": 0, "2027": 0},
                {"2025": 400, "2026": 0, "2027": 0},
                {"2025": 6, "2026": 0, "2027": 0},
                {"2025": 18, "2026": 0, "2027": 0},
                {"2025": 8000, "2026": 10000, "2027": 12000},
                {"2025": 80, "2026": 100, "2027": 120},
                {"2025": 120, "2026": 150, "2027": 540},
                {"2025": 12000, "2026": 15000, "2027": 18000},
                {"2025": 12, "2026": 15, "2027": 18},
                {"2025": 18, "2026": 22.5, "2027": 81},
                {"2025": 8000, "2026": 0, "2027": 0},
                {"2025": 80, "2026": 0, "2027": 0},
                {"2025": 120, "2026": 0, "2027": 0},
                {"2025": 12000, "2026": 0, "2027": 0},
                {"2025": 12, "2026": 0, "2027": 0},
                {"2025": 18, "2026": 0, "2027": 0}]],
             [[
                 {"2025": 400, "2026": 500, "2027": 600},
                 {"2025": 40, "2026": 50, "2027": 60},
                 {"2025": 120, "2026": 150, "2027": 180},
                 {"2025": 400, "2026": 500, "2027": 600},
                 {"2025": 6, "2026": 7.5, "2027": 9},
                 {"2025": 18, "2026": 22.5, "2027": 27},
                 {"2025": 400, "2026": 166.67, "2027": 240},
                 {"2025": 40, "2026": 16.67, "2027": 24},
                 {"2025": 120, "2026": 50, "2027": 72},
                 {"2025": 400, "2026": 166.67, "2027": 240},
                 {"2025": 6, "2026": 2.5, "2027": 3.6},
                 {"2025": 18, "2026": 7.5, "2027": 10.8},
                 {"2025": 8000, "2026": 10000, "2027": 12000},
                 {"2025": 80, "2026": 100, "2027": 120},
                 {"2025": 120, "2026": 150, "2027": 540},
                 {"2025": 12000, "2026": 15000, "2027": 18000},
                 {"2025": 12, "2026": 15, "2027": 18},
                 {"2025": 18, "2026": 22.5, "2027": 81},
                 {"2025": 8000, "2026": 3333.33, "2027": 4800},
                 {"2025": 80, "2026": 33.33, "2027": 48},
                 {"2025": 120, "2026": 50, "2027": 216},
                 {"2025": 12000, "2026": 5000, "2027": 7200},
                 {"2025": 12, "2026": 5, "2027": 7.2},
                 {"2025": 18, "2026": 7.5, "2027": 32.4}],
                 [
                 {"2025": 400, "2026": 500, "2027": 600},
                 {"2025": 40, "2026": 50, "2027": 60},
                 {"2025": 120, "2026": 150, "2027": 180},
                 {"2025": 48, "2026": 120, "2027": 216},
                 {"2025": 35.92, "2026": 40.41, "2027": 43.1088},
                 {"2025": 107.76, "2026": 121.24, "2027": 129.3264},
                 {"2025": 48, "2026": 60, "2027": 72},
                 {"2025": 4.8, "2026": 6, "2027": 7.2},
                 {"2025": 14.4, "2026": 18.0, "2027": 21.6},
                 {"2025": 48, "2026": 60, "2027": 72},
                 {"2025": 0.72, "2026": 0.90, "2027": 1.08},
                 {"2025": 2.16, "2026": 2.70, "2027": 3.24},
                 {"2025": 8000, "2026": 10000, "2027": 12000},
                 {"2025": 80, "2026": 100, "2027": 120},
                 {"2025": 120, "2026": 150, "2027": 540},
                 {"2025": 8480, "2026": 11200, "2027": 14160},
                 {"2025": 71.84, "2026": 80.82, "2027": 86.2176},
                 {"2025": 107.76, "2026": 121.24, "2027": 387.9792},
                 {"2025": 960, "2026": 1200, "2027": 1440},
                 {"2025": 9.6, "2026": 12.0, "2027": 14.4},
                 {"2025": 14.4, "2026": 18.0, "2027": 64.8},
                 {"2025": 1440, "2026": 1800, "2027": 2160},
                 {"2025": 1.44, "2026": 1.80, "2027": 2.16},
                 {"2025": 2.16, "2026": 2.70, "2027": 9.72}]]],
            [[[
                {"2020": 700, "2021": 800, "2022": 900},
                {"2020": 70, "2021": 80, "2022": 90},
                {"2020": 210, "2021": 240, "2022": 270},
                {"2020": 700, "2021": 800, "2022": 900},
                {"2020": 52.5, "2021": 60, "2022": 67.5},
                {"2020": 157.5, "2021": 180.0, "2022": 202.5},
                {"2020": 700, "2021": 760, "2022": 90},
                {"2020": 70, "2021": 76, "2022": 9},
                {"2020": 210, "2021": 228, "2022": 27},
                {"2020": 700, "2021": 760, "2022": 90},
                {"2020": 52.50, "2021": 57.00, "2022": 6.75},
                {"2020": 157.50, "2021": 171.0, "2022": 20.25},
                {"2020": 21000, "2021": 24000, "2022": 27000},
                {"2020": 140, "2021": 160, "2022": 180},
                {"2020": 210, "2021": 240, "2022": 270},
                {"2020": 28000, "2021": 32000, "2022": 36000},
                {"2020": 105, "2021": 120, "2022": 135},
                {"2020": 157.5, "2021": 180.0, "2022": 202.5},
                {"2020": 21000, "2021": 22800, "2022": 2700},
                {"2020": 140, "2021": 152, "2022": 18.0},
                {"2020": 210, "2021": 228, "2022": 27.0},
                {"2020": 28000, "2021": 30400, "2022": 3600},
                {"2020": 105.0, "2021": 114.0, "2022": 13.5},
                {"2020": 157.50, "2021": 171.00, "2022": 20.25}],
                [
                {"2020": 700, "2021": 800, "2022": 900},
                {"2020": 70, "2021": 80, "2022": 90},
                {"2020": 210, "2021": 240, "2022": 270},
                {"2020": 700, "2021": 800, "2022": 900},
                {"2020": 52.5, "2021": 60, "2022": 67.5},
                {"2020": 157.5, "2021": 180, "2022": 202.5},
                {"2020": 700, "2021": 0, "2022": 0},
                {"2020": 70, "2021": 0, "2022": 0},
                {"2020": 210, "2021": 0, "2022": 0},
                {"2020": 700, "2021": 0, "2022": 0},
                {"2020": 52.5, "2021": 0, "2022": 0},
                {"2020": 157.5, "2021": 0, "2022": 0},
                {"2020": 21000, "2021": 24000, "2022": 27000},
                {"2020": 140, "2021": 160, "2022": 180},
                {"2020": 210, "2021": 240, "2022": 270},
                {"2020": 28000, "2021": 32000, "2022": 36000},
                {"2020": 105, "2021": 120, "2022": 135},
                {"2020": 157.5, "2021": 180.0, "2022": 202.5},
                {"2020": 21000, "2021": 0, "2022": 0},
                {"2020": 140, "2021": 0, "2022": 0},
                {"2020": 210, "2021": 0, "2022": 0},
                {"2020": 28000, "2021": 0, "2022": 0},
                {"2020": 105, "2021": 0, "2022": 0},
                {"2020": 157.5, "2021": 0, "2022": 0}]],
             [[
                 {"2020": 700, "2021": 800, "2022": 900},
                 {"2020": 70, "2021": 80, "2022": 90},
                 {"2020": 210, "2021": 240, "2022": 270},
                 {"2020": 700, "2021": 800, "2022": 890},
                 {"2020": 52.5, "2021": 60, "2022": 67.5},
                 {"2020": 157.5, "2021": 180.0, "2022": 202.5},
                 {"2020": 700, "2021": 760, "2022": 90},
                 {"2020": 70, "2021": 76, "2022": 9},
                 {"2020": 210, "2021": 228, "2022": 27},
                 {"2020": 700, "2021": 760, "2022": 90},
                 {"2020": 52.50, "2021": 57.00, "2022": 6.75},
                 {"2020": 157.50, "2021": 171.0, "2022": 20.25},
                 {"2020": 21000, "2021": 24000, "2022": 27000},
                 {"2020": 140, "2021": 160, "2022": 180},
                 {"2020": 210, "2021": 240, "2022": 270},
                 {"2020": 28000, "2021": 32000, "2022": 35900},
                 {"2020": 105, "2021": 120, "2022": 135},
                 {"2020": 157.5, "2021": 180.0, "2022": 202.5},
                 {"2020": 21000, "2021": 22800, "2022": 2700},
                 {"2020": 140, "2021": 152, "2022": 18.0},
                 {"2020": 210, "2021": 228, "2022": 27.0},
                 {"2020": 28000, "2021": 30400, "2022": 3600},
                 {"2020": 105.0, "2021": 114.0, "2022": 13.5},
                 {"2020": 157.50, "2021": 171.00, "2022": 20.25}],
                 [
                 {"2020": 700, "2021": 800, "2022": 900},
                 {"2020": 70, "2021": 80, "2022": 90},
                 {"2020": 210, "2021": 240, "2022": 270},
                 {"2020": 84, "2021": 192, "2022": 324},
                 {"2020": 67.90, "2021": 75.49, "2022": 82.548},
                 {"2020": 203.70, "2021": 226.46, "2022": 247.644},
                 {"2020": 84, "2021": 96, "2022": 108},
                 {"2020": 8.4, "2021": 9.6, "2022": 10.8},
                 {"2020": 25.2, "2021": 28.8, "2022": 32.4},
                 {"2020": 84, "2021": 96, "2022": 108},
                 {"2020": 6.3, "2021": 7.2, "2022": 8.1},
                 {"2020": 18.9, "2021": 21.6, "2022": 24.3},
                 {"2020": 21000, "2021": 24000, "2022": 27000},
                 {"2020": 140, "2021": 160, "2022": 180},
                 {"2020": 210, "2021": 240, "2022": 270},
                 {"2020": 21840, "2021": 25920, "2022": 30240},
                 {"2020": 135.8, "2021": 150.98, "2022": 165.096},
                 {"2020": 203.70, "2021": 226.46, "2022": 247.644},
                 {"2020": 2520, "2021": 2880, "2022": 3240},
                 {"2020": 16.8, "2021": 19.2, "2022": 21.6},
                 {"2020": 25.2, "2021": 28.8, "2022": 32.4},
                 {"2020": 3360, "2021": 3840, "2022": 4320},
                 {"2020": 12.6, "2021": 14.4, "2022": 16.2},
                 {"2020": 18.9, "2021": 21.6, "2022": 24.3}]]]]

    def test_ok(self):
        """Test the 'partition_microsegment' function given valid inputs.

        Raises:
            AssertionError: If function yields unexpected results.
        """
        # Loop through 'ok_out' elements
        for elem in range(0, len(self.ok_out)):
            # Reset AEO time horizon and market entry/exit years
            self.measure_instance.handyvars.aeo_years = \
                self.time_horizons[elem]
            self.measure_instance.market_entry_year = \
                int(self.time_horizons[elem][0])
            self.measure_instance.market_exit_year = \
                int(self.time_horizons[elem][-1]) + 1
            ok_tsv_scale_fracs_in = {
              "energy": {"efficient": {
                  yr: 1 for yr in self.measure_instance.handyvars.aeo_years}},
              "cost": {"baseline": 1, "efficient": {
                  yr: 1 for yr in self.measure_instance.handyvars.aeo_years}},
              "carbon": {"baseline": 1, "efficient": {
                  yr: 1 for yr in self.measure_instance.handyvars.aeo_years}}}
            # Loop through two test schemes (Technical potential and Max
            # adoption potential)
            for scn in range(0, len(self.handyvars.adopt_schemes)):
                # Loop through two microsegment key chains (one applying
                # to new structure type, another to existing structure type)
                for k in range(0, len(self.ok_mskeys_in)):
                    # List of output dicts generated by the function
                    lists1 = self.measure_instance.partition_microsegment(
                        self.handyvars.adopt_schemes[scn],
                        self.ok_diffuse_params_in,
                        self.ok_mskeys_in[k],
                        self.ok_mkt_scale_frac_in,
                        self.ok_new_bldg_constr[elem],
                        self.ok_stock_in[elem], self.ok_energy_in[elem],
                        self.ok_carb_in[elem],
                        self.ok_base_cost_in[elem], self.ok_cost_meas_in[elem],
                        self.ok_cost_energy_base_in,
                        self.ok_cost_energy_meas_in,
                        self.ok_relperf_in[elem],
                        self.ok_life_base_in,
                        self.ok_life_meas_in,
                        self.ok_ssconv_base_in, self.ok_ssconv_meas_in,
                        self.ok_carbint_base_in, self.ok_carbint_meas_in,
                        self.ok_energy_scnd_in[elem],
                        ok_tsv_scale_fracs_in)
                    # Correct list of output dicts
                    lists2 = self.ok_out[elem][scn][k]
                    # Compare each element of the lists of output dicts
                    for elem2 in range(0, len(lists1)):
                        self.dict_check(lists1[elem2], lists2[elem2])


class CheckMarketsTest(unittest.TestCase, CommonMethods):
    """Test 'check_mkt_inputs' function.

    Ensure that the function properly raises a ValueError when
    a measure's applicable baseline market input names are invalid.

    Attributes:
        sample_measure_fail (dict): Sample measures with applicable
            baseline market input names that should yield an error.
    """

    @classmethod
    def setUpClass(cls):
        # Base directory
        base_dir = os.getcwd()
        handyvars = ecm_prep.UsefulVars(base_dir,
                                        ecm_prep.UsefulInputFiles())
        sample_measures_fail = [{
            "name": "sample measure 5",
            "market_entry_year": None,
            "market_exit_year": None,
            "installed_cost": 999,
            "cost_units": "dummy",
            "energy_efficiency": {
                "primary": 999, "secondary": None},
            "energy_efficiency_units": {
                "primary": "dummy", "secondary": None},
            "product_lifetime": 999,
            "climate_zone": "all",
            "bldg_type": "all commercial",
            "structure_type": "all",
            "fuel_type": {
                "primary": [
                    "electricity", "natty gas"],
                "secondary": None},
            "fuel_switch_to": None,
            "end_use": {
                "primary": [
                    "heating", "water heating"],
                "secondary": None},
            "technology": {
                "primary": [
                    "all heating", "electric WH"],
                "secondary": None}},
            {
            "name": "sample measure 6",
            "market_entry_year": None,
            "market_exit_year": None,
            "installed_cost": 999,
            "cost_units": "dummy",
            "energy_efficiency": {
                "primary": 999, "secondary": None},
            "energy_efficiency_units": {
                "primary": "dummy", "secondary": None},
            "product_lifetime": 999,
            "climate_zone": "all",
            "bldg_type": ["assembling", "education"],
            "structure_type": "all",
            "fuel_type": {
                "primary": "natural gas",
                "secondary": None},
            "fuel_switch_to": None,
            "end_use": {
                "primary": "heating",
                "secondary": None},
            "technology": {
                "primary": "all",
                "secondary": None}}]
        cls.sample_measures_fail = [ecm_prep.Measure(
            handyvars, **x) for x in sample_measures_fail]

    def test_invalid_mkts(self):
        """Test 'check_mkt_inputs' function given invalid inputs."""
        for m in self.sample_measures_fail:
            with self.assertRaises(ValueError):
                m.check_mkt_inputs()


class FillParametersTest(unittest.TestCase, CommonMethods):
    """Test 'fill_attr' function.

    Ensure that the function properly converts user-defined 'all'
    climate zone, building type, fuel type, end use, and technology
    attributes to the expanded set of names needed to retrieve measure
    stock, energy, and technology characteristics data.

    Attributes:
        sample_measure_in (dict): Sample measures with attributes
            including 'all' to fill out.
        ok_primary_cpl_out (list): List of cost, performance, and
            lifetime attributes that should be yielded by the function
            for the first two sample measures, given valid inputs.
        ok_primary_mkts_out (list): List of climate zone, building
            type, primary fuel, primary end use, and primary technology
            attributes that should be yielded by the function for each
            of the sample measures, given valid inputs.
    """

    @classmethod
    def setUpClass(cls):
        """Define variables and objects for use across all class functions."""
        # Base directory
        base_dir = os.getcwd()
        handyvars = ecm_prep.UsefulVars(base_dir,
                                        ecm_prep.UsefulInputFiles())
        sample_measures = [{
            "name": "sample measure 1",
            "market_entry_year": None,
            "market_exit_year": None,
            "installed_cost": {
                "all residential": 1,
                "all commercial": 2},
            "cost_units": {
                "all residential": "cost unit 1",
                "all commercial": "cost unit 2"},
            "energy_efficiency": {
                "all residential": {
                    "heating": 111, "cooling": 111},
                "all commercial": 222},
            "energy_efficiency_units": {
                "all residential": "energy unit 1",
                "all commercial": "energy unit 2"},
            "product_lifetime": {
                "all residential": 11,
                "all commercial": 22},
            "climate_zone": "all",
            "bldg_type": "all",
            "structure_type": "all",
            "fuel_type": "all",
            "fuel_switch_to": None,
            "end_use": "all",
            "technology": "all"},
            {
            "name": "sample measure 2",
            "market_entry_year": None,
            "market_exit_year": None,
            "installed_cost": {
                "all residential": 1,
                "assembly": 2,
                "education": 2},
            "cost_units": {
                "all residential": "cost unit 1",
                "assembly": "cost unit 2",
                "education": "cost unit 2"},
            "energy_efficiency": {
                "all residential": {
                    "heating": 111, "cooling": 111},
                "assembly": 222,
                "education": 222},
            "energy_efficiency_units": {
                "all residential": "energy unit 1",
                "assembly": "energy unit 2",
                "education": "energy unit 2"},
            "product_lifetime": {
                "all residential": 11,
                "assembly": 22,
                "education": 22},
            "climate_zone": "all",
            "bldg_type": [
                "all residential", "assembly", "education"],
            "structure_type": "all",
            "fuel_type": "all",
            "fuel_switch_to": None,
            "end_use": "all",
            "technology": "all"},
            {
            "name": "sample measure 3",
            "market_entry_year": None,
            "market_exit_year": None,
            "installed_cost": 999,
            "cost_units": "dummy",
            "energy_efficiency": 999,
            "energy_efficiency_units": "dummy",
            "product_lifetime": 999,
            "climate_zone": "all",
            "bldg_type": "all",
            "structure_type": "all",
            "fuel_type": "all",
            "fuel_switch_to": None,
            "end_use": [
                "heating", "cooling", "secondary heating"],
            "technology": "all"},
            {
            "name": "sample measure 4",
            "market_entry_year": None,
            "market_exit_year": None,
            "installed_cost": 999,
            "cost_units": "dummy",
            "energy_efficiency": 999,
            "energy_efficiency_units": "dummy",
            "product_lifetime": 999,
            "climate_zone": "all",
            "bldg_type": "all residential",
            "structure_type": "all",
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": [
                "lighting", "water heating"],
            "technology": "all"},
            {
            "name": "sample measure 5",
            "market_entry_year": None,
            "market_exit_year": None,
            "installed_cost": 999,
            "cost_units": "dummy",
            "energy_efficiency": {
                "primary": 999, "secondary": None},
            "energy_efficiency_units": {
                "primary": "dummy", "secondary": None},
            "product_lifetime": 999,
            "climate_zone": "all",
            "bldg_type": "all commercial",
            "structure_type": "all",
            "fuel_type": [
                "electricity", "natural gas"],
            "fuel_switch_to": None,
            "end_use": [
                "heating", "water heating"],
            "technology": [
                "all heating", "electric WH"]},
            {
            "name": "sample measure 6",
            "market_entry_year": None,
            "market_exit_year": None,
            "installed_cost": 999,
            "cost_units": "dummy",
            "energy_efficiency": 999,
            "energy_efficiency_units": "dummy",
            "product_lifetime": 999,
            "climate_zone": "all",
            "bldg_type": ["assembly", "education"],
            "structure_type": "all",
            "fuel_type": "natural gas",
            "fuel_switch_to": None,
            "end_use": "heating",
            "technology": "all"},
            {
            "name": "sample measure 7",
            "market_entry_year": None,
            "market_exit_year": None,
            "installed_cost": 999,
            "cost_units": "dummy",
            "energy_efficiency": 999,
            "energy_efficiency_units": "dummy",
            "product_lifetime": 999,
            "climate_zone": "all",
            "bldg_type": [
                "all residential", "small office"],
            "structure_type": "all",
            "fuel_type": "natural gas",
            "fuel_switch_to": None,
            "end_use": "heating",
            "technology": "all"},
            {
            "name": "sample measure 8",
            "market_entry_year": None,
            "market_exit_year": None,
            "installed_cost": 999,
            "cost_units": "dummy",
            "energy_efficiency": 999,
            "energy_efficiency_units": "dummy",
            "product_lifetime": 999,
            "climate_zone": "all",
            "bldg_type": "small office",
            "structure_type": "all",
            "fuel_type": "natural gas",
            "fuel_switch_to": None,
            "end_use": "heating",
            "technology": "all"}]
        cls.sample_measures_in = [ecm_prep.Measure(
            handyvars, **x) for x in sample_measures]
        cls.ok_primary_cpl_out = [[{
            'assembly': 2, 'education': 2, 'food sales': 2,
            'food service': 2, 'health care': 2,
            'large office': 2, 'lodging': 2, 'mercantile/service': 2,
            'mobile home': 1, 'multi family home': 1, 'other': 2,
            'single family home': 1, 'small office': 2, 'warehouse': 2},
            {
            'assembly': "cost unit 2", 'education': "cost unit 2",
            'food sales': "cost unit 2",
            'food service': "cost unit 2", 'health care': "cost unit 2",
            'large office': "cost unit 2", 'lodging': "cost unit 2",
            'mercantile/service': "cost unit 2",
            'mobile home': "cost unit 1",
            'multi family home': "cost unit 1", 'other': "cost unit 2",
            'single family home': "cost unit 1",
            'small office': "cost unit 2", 'warehouse': "cost unit 2"},
            {
            'assembly': 222, 'education': 222, 'food sales': 222,
            'food service': 222, 'health care': 222,
            'large office': 222, 'lodging': 222, 'mercantile/service': 222,
            'mobile home': {"heating": 111, "cooling": 111},
            'multi family home': {"heating": 111, "cooling": 111},
            'other': 222,
            'single family home': {"heating": 111, "cooling": 111},
            'small office': 222, 'warehouse': 222},
            {
            'assembly': "energy unit 2", 'education': "energy unit 2",
            'food sales': "energy unit 2",
            'food service': "energy unit 2", 'health care': "energy unit 2",
            'large office': "energy unit 2", 'lodging': "energy unit 2",
            'mercantile/service': "energy unit 2",
            'mobile home': "energy unit 1",
            'multi family home': "energy unit 1", 'other': "energy unit 2",
            'single family home': "energy unit 1",
            'small office': "energy unit 2", 'warehouse': "energy unit 2"},
            {
            'assembly': 22, 'education': 22, 'food sales': 22,
            'food service': 22, 'health care': 22,
            'large office': 22, 'lodging': 22, 'mercantile/service': 22,
            'mobile home': 11, 'multi family home': 11, 'other': 22,
            'single family home': 11, 'small office': 22,
            'warehouse': 22}],
            [{
             'assembly': 2, 'education': 2, 'mobile home': 1,
             'multi family home': 1, 'single family home': 1},
             {
             'assembly': "cost unit 2", 'education': "cost unit 2",
             'mobile home': "cost unit 1", 'multi family home': "cost unit 1",
             'single family home': "cost unit 1"},
             {
             'assembly': 222, 'education': 222,
             'mobile home': {"heating": 111, "cooling": 111},
             'multi family home': {"heating": 111, "cooling": 111},
             'single family home': {"heating": 111, "cooling": 111}},
             {
             'assembly': "energy unit 2", 'education': "energy unit 2",
             'mobile home': "energy unit 1",
             'multi family home': "energy unit 1",
             'single family home': "energy unit 1"},
             {
             'assembly': 22, 'education': 22, 'mobile home': 11,
             'multi family home': 11, 'single family home': 11}]]
        cls.ok_primary_mkts_out = [[
            ["AIA_CZ1", "AIA_CZ2", "AIA_CZ3", "AIA_CZ4", "AIA_CZ5"],
            ["single family home", "multi family home", "mobile home",
             "assembly", "education", "food sales", "food service",
             "health care", "lodging", "large office", "small office",
             "mercantile/service", "warehouse", "other"],
            ["new", "existing"],
            ["electricity", "natural gas", "distillate", "other fuel"],
            ['drying', 'other (grid electric)', 'water heating',
             'cooling', 'cooking', 'computers', 'lighting',
             'secondary heating', 'TVs', 'heating', 'refrigeration',
             'fans & pumps', 'ceiling fan', 'ventilation', 'MELs',
             'non-PC office equipment', 'PCs'],
            ['dishwasher', 'other MELs',
             'clothes washing', 'freezers',
             'solar WH', 'electric WH',
             'room AC', 'ASHP', 'GSHP', 'central AC',
             'desktop PC', 'laptop PC', 'network equipment',
             'monitors',
             'linear fluorescent (T-8)',
             'linear fluorescent (T-12)',
             'reflector (LED)', 'general service (CFL)',
             'external (high pressure sodium)',
             'general service (incandescent)',
             'external (CFL)',
             'external (LED)', 'reflector (CFL)',
             'reflector (incandescent)',
             'general service (LED)',
             'external (incandescent)',
             'linear fluorescent (LED)',
             'reflector (halogen)',
             'non-specific',
             'home theater & audio', 'set top box',
             'video game consoles', 'DVD', 'TV',
             'resistance heat',
             'NGHP', 'furnace (NG)', 'boiler (NG)',
             'boiler (distillate)', 'furnace (distillate)',
             'resistance', 'furnace (kerosene)',
             'stove (wood)', 'furnace (LPG)',
             'secondary heating (wood)',
             'secondary heating (coal)',
             'secondary heating (kerosene)',
             'secondary heating (LPG)',
             'VAV_Vent', 'CAV_Vent',
             'Solar water heater', 'HP water heater',
             'elec_booster_water_heater',
             'elec_water_heater',
             'rooftop_AC', 'scroll_chiller',
             'res_type_central_AC', 'reciprocating_chiller',
             'comm_GSHP-cool', 'centrifugal_chiller',
             'rooftop_ASHP-cool', 'wall-window_room_AC',
             'screw_chiller',
             'electric_res-heat', 'comm_GSHP-heat',
             'rooftop_ASHP-heat', 'elec_boiler',
             'Commercial Beverage Merchandisers',
             'Commercial Compressor Rack Systems', 'Commercial Condensers',
             'Commercial Ice Machines', 'Commercial Reach-In Freezers',
             'Commercial Reach-In Refrigerators',
             'Commercial Refrigerated Vending Machines',
             'Commercial Supermarket Display Cases',
             'Commercial Walk-In Freezers',
             'Commercial Walk-In Refrigerators',
             'lab fridges and freezers',
             'non-road electric vehicles',
             'kitchen ventilation', 'escalators',
             'distribution transformers',
             'large video displays', 'video displays',
             'elevators', 'laundry', 'medical imaging',
             'coffee brewers', 'fume hoods',
             'security systems',
             '100W A19 Incandescent', '100W Equivalent A19 Halogen',
             '100W Equivalent CFL Bare Spiral', '100W Equivalent LED A Lamp',
             'Halogen Infrared Reflector (HIR) PAR38', 'Halogen PAR38',
             'LED Integrated Luminaire', 'LED PAR38', 'Mercury Vapor',
             'Metal Halide', 'Sodium Vapor', 'SodiumVapor', 'T5 F28',
             'T5 4xF54 HO High Bay', 'T8 F28 High-efficiency/High-Output',
             'T8 F32 Commodity', 'T8 F59 High Efficiency',
             'T8 F59 Typical Efficiency', 'T8 F96 High Output',
             'Range, Electric-induction, 4 burner, oven, ',
             'Range, Electric, 4 burner, oven, 11 griddle',
             'gas_eng-driven_RTAC', 'gas_chiller',
             'res_type_gasHP-cool',
             'gas_eng-driven_RTHP-cool',
             'gas_water_heater', 'gas_instantaneous_WH',
             'gas_booster_WH',
             'Range, Gas, 4 powered burners, convect. ove',
             'Range, Gas, 4 burner, oven, 11 griddle     ',
             'gas_eng-driven_RTHP-heat',
             'res_type_gasHP-heat', 'gas_boiler',
             'gas_furnace', 'oil_water_heater',
             'oil_boiler', 'oil_furnace', None]],
            [
            ["AIA_CZ1", "AIA_CZ2", "AIA_CZ3", "AIA_CZ4", "AIA_CZ5"],
            ["single family home", "multi family home", "mobile home",
             "assembly", "education"],
            ["new", "existing"],
            ["electricity", "natural gas", "distillate", "other fuel"],
            ['drying', 'other (grid electric)', 'water heating',
             'cooling', 'cooking', 'computers', 'lighting',
             'secondary heating', 'TVs', 'heating', 'refrigeration',
             'fans & pumps', 'ceiling fan', 'ventilation', 'MELs',
             'non-PC office equipment', 'PCs'],
            ['dishwasher', 'other MELs',
             'clothes washing', 'freezers',
             'solar WH', 'electric WH',
             'room AC', 'ASHP', 'GSHP', 'central AC',
             'desktop PC', 'laptop PC', 'network equipment',
             'monitors',
             'linear fluorescent (T-8)',
             'linear fluorescent (T-12)',
             'reflector (LED)', 'general service (CFL)',
             'external (high pressure sodium)',
             'general service (incandescent)',
             'external (CFL)',
             'external (LED)', 'reflector (CFL)',
             'reflector (incandescent)',
             'general service (LED)',
             'external (incandescent)',
             'linear fluorescent (LED)',
             'reflector (halogen)',
             'non-specific',
             'home theater & audio', 'set top box',
             'video game consoles', 'DVD', 'TV',
             'resistance heat',
             'NGHP', 'furnace (NG)', 'boiler (NG)',
             'boiler (distillate)', 'furnace (distillate)',
             'resistance', 'furnace (kerosene)',
             'stove (wood)', 'furnace (LPG)',
             'secondary heating (wood)',
             'secondary heating (coal)',
             'secondary heating (kerosene)',
             'secondary heating (LPG)',
             'VAV_Vent', 'CAV_Vent',
             'Solar water heater', 'HP water heater',
             'elec_booster_water_heater',
             'elec_water_heater',
             'rooftop_AC', 'scroll_chiller',
             'res_type_central_AC', 'reciprocating_chiller',
             'comm_GSHP-cool', 'centrifugal_chiller',
             'rooftop_ASHP-cool', 'wall-window_room_AC',
             'screw_chiller',
             'electric_res-heat', 'comm_GSHP-heat',
             'rooftop_ASHP-heat', 'elec_boiler',
             'Commercial Beverage Merchandisers',
             'Commercial Compressor Rack Systems', 'Commercial Condensers',
             'Commercial Ice Machines', 'Commercial Reach-In Freezers',
             'Commercial Reach-In Refrigerators',
             'Commercial Refrigerated Vending Machines',
             'Commercial Supermarket Display Cases',
             'Commercial Walk-In Freezers',
             'Commercial Walk-In Refrigerators',
             'lab fridges and freezers',
             'non-road electric vehicles',
             'kitchen ventilation', 'escalators',
             'distribution transformers',
             'large video displays', 'video displays',
             'elevators', 'laundry', 'medical imaging',
             'coffee brewers', 'fume hoods',
             'security systems',
             '100W A19 Incandescent', '100W Equivalent A19 Halogen',
             '100W Equivalent CFL Bare Spiral', '100W Equivalent LED A Lamp',
             'Halogen Infrared Reflector (HIR) PAR38', 'Halogen PAR38',
             'LED Integrated Luminaire', 'LED PAR38', 'Mercury Vapor',
             'Metal Halide', 'Sodium Vapor', 'SodiumVapor', 'T5 F28',
             'T5 4xF54 HO High Bay', 'T8 F28 High-efficiency/High-Output',
             'T8 F32 Commodity', 'T8 F59 High Efficiency',
             'T8 F59 Typical Efficiency', 'T8 F96 High Output',
             'Range, Electric-induction, 4 burner, oven, ',
             'Range, Electric, 4 burner, oven, 11 griddle',
             'gas_eng-driven_RTAC', 'gas_chiller',
             'res_type_gasHP-cool',
             'gas_eng-driven_RTHP-cool',
             'gas_water_heater', 'gas_instantaneous_WH',
             'gas_booster_WH',
             'Range, Gas, 4 powered burners, convect. ove',
             'Range, Gas, 4 burner, oven, 11 griddle     ',
             'gas_eng-driven_RTHP-heat',
             'res_type_gasHP-heat', 'gas_boiler',
             'gas_furnace', 'oil_water_heater',
             'oil_boiler', 'oil_furnace', None]],
            [
            ["AIA_CZ1", "AIA_CZ2", "AIA_CZ3", "AIA_CZ4", "AIA_CZ5"],
            ["single family home", "multi family home", "mobile home",
             "assembly", "education", "food sales", "food service",
             "health care", "lodging", "large office", "small office",
             "mercantile/service", "warehouse", "other"],
            ["new", "existing"],
            ["electricity", "natural gas", "distillate", "other fuel"],
            ['cooling', 'secondary heating', 'heating'],
            ['rooftop_AC', 'scroll_chiller',
             'res_type_central_AC', 'reciprocating_chiller',
             'comm_GSHP-cool', 'centrifugal_chiller',
             'rooftop_ASHP-cool', 'wall-window_room_AC',
             'screw_chiller', 'electric_res-heat',
             'comm_GSHP-heat', 'rooftop_ASHP-heat', 'elec_boiler',
             'non-specific', 'furnace (NG)', 'boiler (NG)',
             'NGHP', 'room AC', 'ASHP', 'GSHP', 'central AC',
             'resistance heat', 'boiler (distillate)',
             'furnace (distillate)', 'resistance', 'furnace (kerosene)',
             'stove (wood)', 'furnace (LPG)',
             'gas_eng-driven_RTAC', 'gas_chiller',
             'res_type_gasHP-cool', 'gas_eng-driven_RTHP-cool',
             'gas_eng-driven_RTHP-heat', 'res_type_gasHP-heat',
             'gas_boiler', 'gas_furnace', 'oil_boiler', 'oil_furnace',
             'secondary heating (wood)', 'secondary heating (coal)',
             'secondary heating (kerosene)', 'secondary heating (LPG)']],
            [
            ["AIA_CZ1", "AIA_CZ2", "AIA_CZ3", "AIA_CZ4", "AIA_CZ5"],
            ["single family home", "multi family home", "mobile home"],
            ["new", "existing"], "electricity",
            ["lighting", "water heating"],
            ['solar WH', 'electric WH', 'linear fluorescent (T-8)',
             'linear fluorescent (T-12)',
             'reflector (LED)', 'general service (CFL)',
             'external (high pressure sodium)',
             'general service (incandescent)',
             'external (CFL)',
             'external (LED)', 'reflector (CFL)',
             'reflector (incandescent)',
             'general service (LED)',
             'external (incandescent)',
             'linear fluorescent (LED)',
             'reflector (halogen)']],
            [
            ["AIA_CZ1", "AIA_CZ2", "AIA_CZ3", "AIA_CZ4", "AIA_CZ5"],
            ["assembly", "education", "food sales", "food service",
             "health care", "lodging", "large office", "small office",
             "mercantile/service", "warehouse", "other"],
            ["new", "existing"],
            ["electricity", "natural gas"],
            ["heating", "water heating"],
            ['electric_res-heat', 'comm_GSHP-heat', 'rooftop_ASHP-heat',
             'elec_boiler', 'gas_eng-driven_RTHP-heat', 'res_type_gasHP-heat',
             'gas_boiler', 'gas_furnace', 'electric WH']],
            [
            ["AIA_CZ1", "AIA_CZ2", "AIA_CZ3", "AIA_CZ4", "AIA_CZ5"],
            ["assembly", "education"],
            ["new", "existing"], "natural gas", "heating",
            ["res_type_gasHP-heat", "gas_eng-driven_RTHP-heat",
             "gas_boiler", "gas_furnace"]],
            [
            ["AIA_CZ1", "AIA_CZ2", "AIA_CZ3", "AIA_CZ4", "AIA_CZ5"],
            ["single family home", "multi family home", "mobile home",
             "small office"],
            ["new", "existing"], "natural gas", "heating",
            ["furnace (NG)", "NGHP", "boiler (NG)", "res_type_gasHP-heat",
             "gas_eng-driven_RTHP-heat", "gas_boiler", "gas_furnace"]],
            [
            ["AIA_CZ1", "AIA_CZ2", "AIA_CZ3", "AIA_CZ4", "AIA_CZ5"],
            "small office", ["new", "existing"], "natural gas",
            "heating", [
                "res_type_gasHP-heat", "gas_eng-driven_RTHP-heat",
                "gas_boiler", "gas_furnace"]]]

    def test_fill(self):
        """Test 'fill_attr' function given valid inputs.

        Note:
            Tests that measure attributes containing 'all' are properly
            filled in with the appropriate attribute details.

        Raises:
            AssertionError: If function yields unexpected results.
        """
        # Loop through sample measures
        for ind, m in enumerate(self.sample_measures_in):
            # Execute the function on each sample measure
            m.fill_attr()
            # For the first two sample measures, check that cost, performance,
            # and lifetime attribute dicts with 'all residential' and
            # 'all commercial' keys were properly filled out
            if ind < 2:
                [self.dict_check(x, y) for x, y in zip([
                    m.installed_cost, m.cost_units,
                    m.energy_efficiency["primary"],
                    m.energy_efficiency_units["primary"],
                    m.product_lifetime],
                    [o for o in self.ok_primary_cpl_out[ind]])]
            # For each sample measure, check that 'all' climate zone,
            # building type/vintage, fuel type, end use, and technology
            # attributes were properly filled out
            self.assertEqual([
                sorted(x, key=lambda x: (x is None, x)) if isinstance(x, list)
                else x for x in [
                    m.climate_zone, m.bldg_type, m.structure_type,
                    m.fuel_type['primary'], m.end_use['primary'],
                    m.technology['primary']]],
                [sorted(x, key=lambda x: (x is None, x)) if isinstance(x, list)
                 else x for x in self.ok_primary_mkts_out[ind]])


class CreateKeyChainTest(unittest.TestCase, CommonMethods):
    """Test 'create_keychain' function.

    Ensure that the function yields proper key chain output given
    input microsegment information.

    Attributes:
        sample_measure_in (dict): Sample measure attributes.
        ok_out_primary (list): Primary microsegment key chain that should
            be yielded by the function given valid inputs.
        ok_out_secondary (list): Secondary microsegment key chain that
            should be yielded by the function given valid inputs.
    """

    @classmethod
    def setUpClass(cls):
        """Define variables and objects for use across all class functions."""
        # Base directory
        base_dir = os.getcwd()
        handyvars = ecm_prep.UsefulVars(base_dir,
                                        ecm_prep.UsefulInputFiles())
        sample_measure = {
            "name": "sample measure 2",
            "active": 1,
            "market_entry_year": None,
            "market_exit_year": None,
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": 0.5,
            "energy_efficiency_units": "relative savings (constant)",
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "bldg_type": "single family home",
            "fuel_type": {
                "primary": "electricity",
                "secondary": "electricity"},
            "fuel_switch_to": None,
            "end_use": {
                "primary": ["heating", "cooling"],
                "secondary": "lighting"},
            "technology": {
                "primary": ["resistance heat", "ASHP", "GSHP", "room AC"],
                "secondary": "general service (LED)"},
            "mseg_adjust": {
                "contributing mseg keys and values": {},
                "competed choice parameters": {},
                "secondary mseg adjustments": {
                    "sub-market": {
                        "original energy (total)": {},
                        "adjusted energy (sub-market)": {}},
                    "stock-and-flow": {
                        "original energy (total)": {},
                        "adjusted energy (previously captured)": {},
                        "adjusted energy (competed)": {},
                        "adjusted energy (competed and captured)": {}},
                    "market share": {
                        "original energy (total captured)": {},
                        "original energy (competed and captured)": {},
                        "adjusted energy (total captured)": {},
                        "adjusted energy (competed and captured)": {}}}}}
        cls.sample_measure_in = ecm_prep.Measure(
            handyvars, **sample_measure)
        # Finalize the measure's 'technology_type' attribute (handled by the
        # 'fill_attr' function, which is not run as part of this test)
        cls.sample_measure_in.technology_type = {
            "primary": "supply", "secondary": "supply"}
        cls.ok_out_primary = [
            ('primary', 'AIA_CZ1', 'single family home',
             'electricity', 'heating', 'supply',
             'resistance heat', 'new'),
            ('primary', 'AIA_CZ1', 'single family home',
             'electricity', 'heating', 'supply', 'ASHP',
             'new'),
            ('primary', 'AIA_CZ1', 'single family home',
             'electricity', 'heating', 'supply', 'GSHP',
             'new'),
            ('primary', 'AIA_CZ1', 'single family home',
             'electricity', 'heating', 'supply', 'room AC',
             'new'),
            ('primary', 'AIA_CZ1', 'single family home',
             'electricity', 'cooling', 'supply',
             'resistance heat', 'new'),
            ('primary', 'AIA_CZ1', 'single family home',
             'electricity', 'cooling', 'supply', 'ASHP',
             'new'),
            ('primary', 'AIA_CZ1', 'single family home',
             'electricity', 'cooling', 'supply', 'GSHP',
             'new'),
            ('primary', 'AIA_CZ1', 'single family home',
             'electricity', 'cooling', 'supply', 'room AC',
             'new'),
            ('primary', 'AIA_CZ2', 'single family home',
             'electricity', 'heating', 'supply',
             'resistance heat', 'new'),
            ('primary', 'AIA_CZ2', 'single family home',
             'electricity', 'heating', 'supply', 'ASHP',
             'new'),
            ('primary', 'AIA_CZ2', 'single family home',
             'electricity', 'heating', 'supply', 'GSHP',
             'new'),
            ('primary', 'AIA_CZ2', 'single family home',
             'electricity', 'heating', 'supply', 'room AC',
             'new'),
            ('primary', 'AIA_CZ2', 'single family home',
             'electricity', 'cooling', 'supply',
             'resistance heat', 'new'),
            ('primary', 'AIA_CZ2', 'single family home',
             'electricity', 'cooling', 'supply', 'ASHP',
             'new'),
            ('primary', 'AIA_CZ2', 'single family home',
             'electricity', 'cooling', 'supply', 'GSHP',
             'new'),
            ('primary', 'AIA_CZ2', 'single family home',
             'electricity', 'cooling', 'supply', 'room AC',
             'new'),
            ('primary', 'AIA_CZ1', 'single family home',
             'electricity', 'heating', 'supply',
             'resistance heat', 'existing'),
            ('primary', 'AIA_CZ1', 'single family home',
             'electricity', 'heating', 'supply', 'ASHP',
             'existing'),
            ('primary', 'AIA_CZ1', 'single family home',
             'electricity', 'heating', 'supply', 'GSHP',
             'existing'),
            ('primary', 'AIA_CZ1', 'single family home',
             'electricity', 'heating', 'supply', 'room AC',
             'existing'),
            ('primary', 'AIA_CZ1', 'single family home',
             'electricity', 'cooling', 'supply',
             'resistance heat', 'existing'),
            ('primary', 'AIA_CZ1', 'single family home',
             'electricity', 'cooling', 'supply', 'ASHP',
             'existing'),
            ('primary', 'AIA_CZ1', 'single family home',
             'electricity', 'cooling', 'supply', 'GSHP',
             'existing'),
            ('primary', 'AIA_CZ1', 'single family home',
             'electricity', 'cooling', 'supply', 'room AC',
             'existing'),
            ('primary', 'AIA_CZ2', 'single family home',
             'electricity', 'heating', 'supply',
             'resistance heat', 'existing'),
            ('primary', 'AIA_CZ2', 'single family home',
             'electricity', 'heating', 'supply', 'ASHP',
             'existing'),
            ('primary', 'AIA_CZ2', 'single family home',
             'electricity', 'heating', 'supply', 'GSHP',
             'existing'),
            ('primary', 'AIA_CZ2', 'single family home',
             'electricity', 'heating', 'supply', 'room AC',
             'existing'),
            ('primary', 'AIA_CZ2', 'single family home',
             'electricity', 'cooling', 'supply',
             'resistance heat', 'existing'),
            ('primary', 'AIA_CZ2', 'single family home',
             'electricity', 'cooling', 'supply', 'ASHP',
             'existing'),
            ('primary', 'AIA_CZ2', 'single family home',
             'electricity', 'cooling', 'supply', 'GSHP',
             'existing'),
            ('primary', 'AIA_CZ2', 'single family home',
             'electricity', 'cooling', 'supply', 'room AC',
             'existing')]
        cls.ok_out_secondary = [
            ('secondary', 'AIA_CZ1', 'single family home',
             'electricity', 'lighting',
             'general service (LED)', 'new'),
            ('secondary', 'AIA_CZ2', 'single family home',
             'electricity', 'lighting',
             'general service (LED)', 'new'),
            ('secondary', 'AIA_CZ1', 'single family home',
             'electricity', 'lighting',
             'general service (LED)', 'existing'),
            ('secondary', 'AIA_CZ2', 'single family home',
             'electricity', 'lighting',
             'general service (LED)', 'existing')]

    def test_primary(self):
        """Test 'create_keychain' function given valid inputs.

        Note:
            Tests generation of primary microsegment key chains.

        Raises:
            AssertionError: If function yields unexpected results.
        """
        self.assertEqual(
            self.sample_measure_in.create_keychain("primary")[0],
            self.ok_out_primary)

    # Test the generation of a list of secondary mseg key chains
    def test_secondary(self):
        """Test 'create_keychain' function given valid inputs.

        Note:
            Tests generation of secondary microsegment key chains.

        Raises:
            AssertionError: If function yields unexpected results.
        """
        self.assertEqual(
            self.sample_measure_in.create_keychain("secondary")[0],
            self.ok_out_secondary)


class AddKeyValsTest(unittest.TestCase, CommonMethods):
    """Test 'add_keyvals' and 'add_keyvals_restrict' functions.

    Ensure that the functions properly add together input dictionaries.

    Attributes:
        sample_measure_in (dict): Sample measure attributes.
        ok_dict1_in (dict): Valid sample input dict for 'add_keyvals' function.
        ok_dict2_in (dict): Valid sample input dict for 'add_keyvals' function.
        ok_dict3_in (dict): Valid sample input dict for
            'add_keyvals_restrict' function.
        ok_dict4_in (dict): Valid sample input dict for
            'add_keyvals_restrict' function.
        fail_dict1_in (dict): One of two invalid sample input dicts for
            'add_keyvals' function (dict keys do not exactly match).
        fail_dict2_in (dict): Two of two invalid sample input dicts for
            'add_keyvals' function (dict keys do not exactly match).
        ok_out (dict): Dictionary that should be generated by 'add_keyvals'
            function given valid inputs.
        ok_out_restrict (dict): Dictionary that should be generated by
            'add_keyvals_restrict' function given valid inputs.
    """

    @classmethod
    def setUpClass(cls):
        """Define variables and objects for use across all class functions."""
        # Base directory
        base_dir = os.getcwd()
        handyvars = ecm_prep.UsefulVars(base_dir,
                                        ecm_prep.UsefulInputFiles())
        sample_measure_in = {
            "name": "sample measure 1",
            "active": 1,
            "market_entry_year": None,
            "market_exit_year": None,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "bldg_type": ["single family home"],
            "fuel_type": {
                "primary": ["electricity"],
                "secondary": None},
            "fuel_switch_to": None,
            "end_use": {
                "primary": ["heating", "cooling"],
                "secondary": None},
            "technology": {
                "primary": ["resistance heat", "ASHP", "GSHP", "room AC"],
                "secondary": None}}
        cls.sample_measure_in = ecm_prep.Measure(
            handyvars, **sample_measure_in)
        cls.ok_dict1_in, cls.ok_dict2_in = ({
            "level 1a": {
                "level 2aa": {"2009": 2, "2010": 3},
                "level 2ab": {"2009": 4, "2010": 5}},
            "level 1b": {
                "level 2ba": {"2009": 6, "2010": 7},
                "level 2bb": {"2009": 8, "2010": 9}}} for n in range(2))
        cls.ok_dict3_in, cls.ok_dict4_in = ({
            "level 1a": {
                "level 2aa": {"2009": 2, "2010": 3},
                "level 2ab": {"2009": 4, "2010": 5}},
            "lifetime": {
                "level 2ba": {"2009": 6, "2010": 7},
                "level 2bb": {"2009": 8, "2010": 9}}} for n in range(2))
        cls.fail_dict1_in = {
            "level 1a": {
                "level 2aa": {"2009": 2, "2010": 3},
                "level 2ab": {"2009": 4, "2010": 5}},
            "level 1b": {
                "level 2ba": {"2009": 6, "2010": 7},
                "level 2bb": {"2009": 8, "2010": 9}}}
        cls.fail_dict2_in = {
            "level 1a": {
                "level 2aa": {"2009": 2, "2010": 3},
                "level 2ab": {"2009": 4, "2010": 5}},
            "level 1b": {
                "level 2ba": {"2009": 6, "2010": 7},
                "level 2bb": {"2009": 8, "2011": 9}}}
        cls.ok_out = {
            "level 1a": {
                "level 2aa": {"2009": 4, "2010": 6},
                "level 2ab": {"2009": 8, "2010": 10}},
            "level 1b": {
                "level 2ba": {"2009": 12, "2010": 14},
                "level 2bb": {"2009": 16, "2010": 18}}}
        cls.ok_out_restrict = {
            "level 1a": {
                "level 2aa": {"2009": 4, "2010": 6},
                "level 2ab": {"2009": 8, "2010": 10}},
            "lifetime": {
                "level 2ba": {"2009": 6, "2010": 7},
                "level 2bb": {"2009": 8, "2010": 9}}}

    def test_ok_add_keyvals(self):
        """Test 'add_keyvals' function given valid inputs.

        Raises:
            AssertionError: If function yields unexpected results.
        """
        self.dict_check(
            self.sample_measure_in.add_keyvals(
                self.ok_dict1_in, self.ok_dict2_in), self.ok_out)

    def test_fail_add_keyvals(self):
        """Test 'add_keyvals' function given invalid inputs.

        Raises:
            AssertionError: If KeyError is not raised.
        """
        with self.assertRaises(KeyError):
            self.sample_measure_in.add_keyvals(
                self.fail_dict1_in, self.fail_dict2_in)

    def test_ok_add_keyvals_restrict(self):
        """Test 'add_keyvals_restrict' function given valid inputs."""
        self.dict_check(
            self.sample_measure_in.add_keyvals_restrict(
                self.ok_dict3_in, self.ok_dict4_in), self.ok_out_restrict)


class DivKeyValsTest(unittest.TestCase, CommonMethods):
    """Test 'div_keyvals' function.

    Ensure that the function properly divides the key values of one dict
    by those of another. Test inputs reflect the use of this function
    to generate output partitioning fractions (used to break out
    measure results by climate zone, building sector, end use).

    Attributes:
        sample_measure_in (dict): Sample measure attributes.
        ok_reduce_dict (dict): Values from second dict to normalize first
            dict values by.
        ok_dict_in (dict): Sample input dict with values to normalize.
        ok_out (dict): Output dictionary that should be yielded by the
            function given valid inputs.
    """

    @classmethod
    def setUpClass(cls):
        """Define variables and objects for use across all class functions."""
        # Base directory
        base_dir = os.getcwd()
        handyvars = ecm_prep.UsefulVars(base_dir,
                                        ecm_prep.UsefulInputFiles())
        sample_measure_in = {
            "name": "sample measure 1",
            "active": 1,
            "market_entry_year": None,
            "market_exit_year": None,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "bldg_type": ["single family home"],
            "fuel_type": {
                "primary": ["electricity"],
                "secondary": None},
            "fuel_switch_to": None,
            "end_use": {
                "primary": ["heating", "cooling"],
                "secondary": None},
            "technology": {
                "primary": ["resistance heat", "ASHP", "GSHP", "room AC"],
                "secondary": None}}
        cls.sample_measure_in = ecm_prep.Measure(
            handyvars, **sample_measure_in)
        cls.ok_reduce_dict = {"2009": 100, "2010": 100}
        cls.ok_dict_in = {
            "AIA CZ1": {
                "Residential": {
                    "Heating": {"2009": 10, "2010": 10},
                    "Cooling": {"2009": 15, "2010": 15}},
                "Commercial": {
                    "Heating": {"2009": 20, "2010": 20},
                    "Cooling": {"2009": 25, "2010": 25}}},
            "AIA CZ2": {
                "Residential": {
                    "Heating": {"2009": 30, "2010": 30},
                    "Cooling": {"2009": 35, "2010": 35}},
                "Commercial": {
                    "Heating": {"2009": 40, "2010": 40},
                    "Cooling": {"2009": 45, "2010": 45}}}}
        cls.ok_out = {
            "AIA CZ1": {
                "Residential": {
                    "Heating": {"2009": .10, "2010": .10},
                    "Cooling": {"2009": .15, "2010": .15}},
                "Commercial": {
                    "Heating": {"2009": .20, "2010": .20},
                    "Cooling": {"2009": .25, "2010": .25}}},
            "AIA CZ2": {
                "Residential": {
                    "Heating": {"2009": .30, "2010": .30},
                    "Cooling": {"2009": .35, "2010": .35}},
                "Commercial": {
                    "Heating": {"2009": .40, "2010": .40},
                    "Cooling": {"2009": .45, "2010": .45}}}}

    def test_ok(self):
        """Test 'div_keyvals' function given valid inputs.

        Raises:
            AssertionError: If function yields unexpected results.
        """
        self.dict_check(
            self.sample_measure_in.div_keyvals(
                self.ok_dict_in, self.ok_reduce_dict), self.ok_out)


class DivKeyValsFloatTest(unittest.TestCase, CommonMethods):
    """Test 'div_keyvals_float' and div_keyvals_float_restrict' functions.

    Ensure that the functions properly divide dict key values by a given
    factor.

    Attributes:
        sample_measure_in (dict): Sample measure attributes.
        ok_reduce_num (float): Factor by which dict values should be divided.
        ok_dict_in (dict): Sample input dict with values to divide.
        ok_out (dict): Output dictionary that should be yielded by
            'div_keyvals_float' function given valid inputs.
        ok_out_restrict (dict): Output dictionary that should be yielded by
            'div_keyvals_float_restrict'function given valid inputs.
    """

    @classmethod
    def setUpClass(cls):
        """Define variables and objects for use across all class functions."""
        # Base directory
        base_dir = os.getcwd()
        handyvars = ecm_prep.UsefulVars(base_dir,
                                        ecm_prep.UsefulInputFiles())
        sample_measure_in = {
            "name": "sample measure 1",
            "active": 1,
            "market_entry_year": None,
            "market_exit_year": None,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "bldg_type": ["single family home"],
            "fuel_type": {
                "primary": ["electricity"],
                "secondary": None},
            "fuel_switch_to": None,
            "end_use": {
                "primary": ["heating", "cooling"],
                "secondary": None},
            "technology": {
                "primary": ["resistance heat", "ASHP", "GSHP", "room AC"],
                "secondary": None}}
        cls.sample_measure_in = ecm_prep.Measure(
            handyvars, **sample_measure_in)
        cls.ok_reduce_num = 4
        cls.ok_dict_in = {
            "stock": {
                "total": {"2009": 100, "2010": 200},
                "competed": {"2009": 300, "2010": 400}},
            "energy": {
                "total": {"2009": 500, "2010": 600},
                "competed": {"2009": 700, "2010": 800},
                "efficient": {"2009": 700, "2010": 800}},
            "carbon": {
                "total": {"2009": 500, "2010": 600},
                "competed": {"2009": 700, "2010": 800},
                "efficient": {"2009": 700, "2010": 800}},
            "cost": {
                "baseline": {
                    "stock": {"2009": 900, "2010": 1000},
                    "energy": {"2009": 900, "2010": 1000},
                    "carbon": {"2009": 900, "2010": 1000}},
                "measure": {
                    "stock": {"2009": 1100, "2010": 1200},
                    "energy": {"2009": 1100, "2010": 1200},
                    "carbon": {"2009": 1100, "2010": 1200}}}}
        cls.ok_out = {
            "stock": {
                "total": {"2009": 25, "2010": 50},
                "competed": {"2009": 75, "2010": 100}},
            "energy": {
                "total": {"2009": 125, "2010": 150},
                "competed": {"2009": 175, "2010": 200},
                "efficient": {"2009": 175, "2010": 200}},
            "carbon": {
                "total": {"2009": 125, "2010": 150},
                "competed": {"2009": 175, "2010": 200},
                "efficient": {"2009": 175, "2010": 200}},
            "cost": {
                "baseline": {
                    "stock": {"2009": 225, "2010": 250},
                    "energy": {"2009": 225, "2010": 250},
                    "carbon": {"2009": 225, "2010": 250}},
                "measure": {
                    "stock": {"2009": 275, "2010": 300},
                    "energy": {"2009": 275, "2010": 300},
                    "carbon": {"2009": 275, "2010": 300}}}}
        cls.ok_out_restrict = {
            "stock": {
                "total": {"2009": 25, "2010": 50},
                "competed": {"2009": 75, "2010": 100}},
            "energy": {
                "total": {"2009": 500, "2010": 600},
                "competed": {"2009": 700, "2010": 800},
                "efficient": {"2009": 700, "2010": 800}},
            "carbon": {
                "total": {"2009": 500, "2010": 600},
                "competed": {"2009": 700, "2010": 800},
                "efficient": {"2009": 700, "2010": 800}},
            "cost": {
                "baseline": {
                    "stock": {"2009": 225, "2010": 250},
                    "energy": {"2009": 900, "2010": 1000},
                    "carbon": {"2009": 900, "2010": 1000}},
                "measure": {
                    "stock": {"2009": 275, "2010": 300},
                    "energy": {"2009": 1100, "2010": 1200},
                    "carbon": {"2009": 1100, "2010": 1200}}}}

    def test_ok_div(self):
        """Test 'div_keyvals_float' function given valid inputs.

        Raises:
            AssertionError: If function yields unexpected results.
        """
        self.dict_check(
            self.sample_measure_in.div_keyvals_float(
                copy.deepcopy(self.ok_dict_in), self.ok_reduce_num),
            self.ok_out)

    def test_ok_div_restrict(self):
        """Test 'div_keyvals_float_restrict' function given valid inputs.

        Raises:
            AssertionError: If function yields unexpected results.
        """
        self.dict_check(
            self.sample_measure_in.div_keyvals_float_restrict(
                copy.deepcopy(self.ok_dict_in), self.ok_reduce_num),
            self.ok_out_restrict)


class AppendKeyValsTest(unittest.TestCase):
    """Test 'append_keyvals' function.

    Ensure that the function properly determines a list of valid names
    for describing a measure's applicable baseline market.

    Attributes:
        handyvars (object): Global variables to use for the test measure.
        ok_mktnames_out (list): Set of valid names that should be generated
            by the function given valid inputs.
    """
    @classmethod
    def setUpClass(cls):
        """Define variables and objects for use across all class functions."""
        base_dir = os.getcwd()
        cls.handyvars = ecm_prep.UsefulVars(base_dir,
                                            ecm_prep.UsefulInputFiles())
        cls.ok_mktnames_out = [
            "AIA_CZ1", "AIA_CZ2", "AIA_CZ3", "AIA_CZ4", "AIA_CZ5",
            "single family home",
            "multi family home", "mobile home",
            "assembly", "education", "food sales", "food service",
            "health care", "lodging", "large office", "small office",
            "mercantile/service", "warehouse", "other",
            "electricity", "natural gas", "distillate", "other fuel",
            'drying', 'other (grid electric)', 'water heating',
            'cooling', 'cooking', 'computers', 'lighting',
            'secondary heating', 'TVs', 'heating', 'refrigeration',
            'fans & pumps', 'ceiling fan', 'ventilation', 'MELs',
            'non-PC office equipment', 'PCs',
            'dishwasher', 'other MELs', 'clothes washing', 'freezers',
            'solar WH', 'electric WH', 'room AC', 'ASHP', 'central AC',
            'desktop PC', 'laptop PC', 'network equipment', 'monitors',
            'linear fluorescent (T-8)', 'linear fluorescent (T-12)',
            'reflector (LED)', 'general service (CFL)',
            'external (high pressure sodium)',
            'general service (incandescent)',
            'external (CFL)', 'external (LED)', 'reflector (CFL)',
            'reflector (incandescent)', 'general service (LED)',
            'external (incandescent)', 'linear fluorescent (LED)',
            'reflector (halogen)', 'non-specific', 'home theater & audio',
            'set top box', 'video game consoles', 'DVD', 'TV',
            'GSHP', 'resistance heat', 'NGHP', 'furnace (NG)',
            'boiler (NG)', 'boiler (distillate)', 'furnace (distillate)',
            'resistance', 'furnace (kerosene)', 'stove (wood)',
            'furnace (LPG)', 'secondary heating (wood)',
            'secondary heating (coal)', 'secondary heating (kerosene)',
            'secondary heating (LPG)', 'roof', 'ground', 'windows solar',
            'windows conduction', 'equipment gain', 'people gain', 'wall',
            'infiltration', 'lighting gain', 'floor', 'other heat gain',
            'VAV_Vent', 'CAV_Vent', 'Solar water heater',
            'HP water heater', 'elec_booster_water_heater',
            'elec_water_heater', 'rooftop_AC', 'scroll_chiller',
            'res_type_central_AC', 'reciprocating_chiller', 'comm_GSHP-cool',
            'centrifugal_chiller', 'rooftop_ASHP-cool', 'wall-window_room_AC',
            'screw_chiller', 'electric_res-heat', 'comm_GSHP-heat',
            'rooftop_ASHP-heat', 'elec_boiler',
            'Commercial Beverage Merchandisers',
            'Commercial Compressor Rack Systems', 'Commercial Condensers',
            'Commercial Ice Machines', 'Commercial Reach-In Freezers',
            'Commercial Reach-In Refrigerators',
            'Commercial Refrigerated Vending Machines',
            'Commercial Supermarket Display Cases',
            'Commercial Walk-In Freezers',
            'Commercial Walk-In Refrigerators',
            'lab fridges and freezers',
            'non-road electric vehicles', 'kitchen ventilation',
            'escalators', 'distribution transformers',
            'large video displays', 'video displays', 'elevators', 'laundry',
            'medical imaging', 'coffee brewers', 'fume hoods',
            'security systems',
            '100W A19 Incandescent', '100W Equivalent A19 Halogen',
            '100W Equivalent CFL Bare Spiral', '100W Equivalent LED A Lamp',
            'Halogen Infrared Reflector (HIR) PAR38', 'Halogen PAR38',
            'LED Integrated Luminaire', 'LED PAR38', 'Mercury Vapor',
            'Metal Halide', 'Sodium Vapor', 'SodiumVapor', 'T5 F28',
            'T5 4xF54 HO High Bay', 'T8 F28 High-efficiency/High-Output',
            'T8 F32 Commodity', 'T8 F59 High Efficiency',
            'T8 F59 Typical Efficiency', 'T8 F96 High Output',
            'Range, Electric-induction, 4 burner, oven, ',
            'Range, Electric, 4 burner, oven, 11 griddle',
            'gas_eng-driven_RTAC', 'gas_chiller', 'res_type_gasHP-cool',
            'gas_eng-driven_RTHP-cool', 'gas_water_heater',
            'gas_instantaneous_WH', 'gas_booster_WH',
            'Range, Gas, 4 powered burners, convect. ove',
            'Range, Gas, 4 burner, oven, 11 griddle     ',
            'gas_eng-driven_RTHP-heat', 'res_type_gasHP-heat',
            'gas_boiler', 'gas_furnace', 'oil_water_heater', 'oil_boiler',
            'oil_furnace', 'new', 'existing', 'supply', 'demand',
            'all', 'all residential', 'all commercial', 'all heating',
            'all drying', 'all other (grid electric)',
            'all water heating', 'all cooling', 'all cooking',
            'all computers', 'all lighting', 'all secondary heating',
            'all TVs', 'all refrigeration', 'all fans & pumps',
            'all ceiling fan', 'all ventilation', 'all MELs',
            'all non-PC office equipment', 'all PCs']

    def test_ok_append(self):
        """Test 'append_keyvals' function given valid inputs.

        Raises:
            AssertionError: If function yields unexpected results.
        """
        self.assertEqual(sorted(
            [x for x in self.handyvars.valid_mktnames if x is not None]),
            sorted([x for x in self.ok_mktnames_out if x is not None]))


class CostConversionTest(unittest.TestCase, CommonMethods):
    """Test 'convert_costs' function.

    Ensure that function properly converts user-defined measure cost units
    to align with comparable baseline cost units.

    Attributes:
        verbose (NoneType): Determines whether to print all user messages.
        sample_measure_in (dict): Sample measure attributes.
        sample_convertdata_ok_in (dict): Sample cost conversion input data.
        sample_bldgsect_ok_in (list): List of valid building sectors for
            sample measure cost.
        sample_mskeys_ok_in (list): List of valid full market microsegment
            information for sample measure cost (mseg type->czone->bldg->fuel->
            end use->technology type->structure type).
        sample_mskeys_fail_in (list): List of microsegment information for
            sample measure cost that should cause function to fail.
        cost_meas_ok_in (int): Sample measure cost.
        cost_meas_units_ok_in_yronly (string): List of valid sample measure
            cost units where only the cost year needs adjustment.
        cost_meas_units_ok_in_all (list): List of valid sample measure cost
            units where the cost year and/or units need adjustment.
        cost_meas_units_fail_in (string): List of sample measure cost units
            that should cause the function to fail.
        cost_base_units_ok_in (string): List of valid baseline cost units.
        ok_out_costs_yronly (float): Converted measure costs that should be
            yielded given 'cost_meas_units_ok_in_yronly' measure cost units.
        ok_out_costs_all (list): Converted measure costs that should be
            yielded given 'cost_meas_units_ok_in_all' measure cost units.
        ok_out_cost_units (string): Converted measure cost units that should
            be yielded given valid inputs to the function.
    """

    @classmethod
    def setUpClass(cls):
        """Define variables and objects for use across all class functions."""
        # Base directory
        base_dir = os.getcwd()
        handyvars = ecm_prep.UsefulVars(base_dir,
                                        ecm_prep.UsefulInputFiles())
        sample_measure_in = {
            "name": "sample measure 2",
            "remove": False,
            "market_entry_year": None,
            "market_exit_year": None,
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": 0.5,
            "energy_efficiency_units": "relative savings (constant)",
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "bldg_type": ["single family home"],
            "fuel_type": {
                "primary": ["electricity"],
                "secondary": ["electricity"]},
            "fuel_switch_to": None,
            "end_use": {
                "primary": ["heating", "cooling"],
                "secondary": ["lighting"]},
            "technology": {
                "primary": ["resistance heat", "ASHP", "GSHP", "room AC"],
                "secondary": ["general service (LED)"]},
            "mseg_adjust": {
                "contributing mseg keys and values": {},
                "competed choice parameters": {},
                "secondary mseg adjustments": {
                    "sub-market": {
                        "original energy (total)": {},
                        "adjusted energy (sub-market)": {}},
                    "stock-and-flow": {
                        "original energy (total)": {},
                        "adjusted energy (previously captured)": {},
                        "adjusted energy (competed)": {},
                        "adjusted energy (competed and captured)": {}},
                    "market share": {
                        "original energy (total captured)": {},
                        "original energy (competed and captured)": {},
                        "adjusted energy (total captured)": {},
                        "adjusted energy (competed and captured)": {}}}}}
        cls.verbose = None
        cls.sample_measure_in = ecm_prep.Measure(
            handyvars, **sample_measure_in)
        cls.sample_convertdata_ok_in = {
            "building type conversions": {
                "original type": "EnergyPlus reference buildings",
                "revised type": "Annual Energy Outlook (AEO) buildings",
                "conversion data": {
                    "description": "sample",
                    "value": {
                        "residential": {
                            "single family home": {
                                "Single-Family": 1},
                            "mobile home": {
                                "Single-Family": 1},
                            "multi family home": {
                                "Multifamily": 1}},
                        "commercial": {
                            "assembly": {
                                "Hospital": 1},
                            "education": {
                                "PrimarySchool": 0.26,
                                "SecondarySchool": 0.74},
                            "food sales": {
                                "Supermarket": 1},
                            "food service": {
                                "QuickServiceRestaurant": 0.31,
                                "FullServiceRestaurant": 0.69},
                            "health care": None,
                            "lodging": {
                                "SmallHotel": 0.26,
                                "LargeHotel": 0.74},
                            "large office": {
                                "LargeOffice": 0.9,
                                "MediumOffice": 0.1},
                            "small office": {
                                "SmallOffice": 0.12,
                                "OutpatientHealthcare": 0.88},
                            "mercantile/service": {
                                "RetailStandalone": 0.53,
                                "RetailStripmall": 0.47},
                            "warehouse": {
                                "Warehouse": 1},
                            "other": None}},
                    "source": {
                        "residential": "sample",
                        "commercial": "sample"},
                    "notes": {
                        "residential": "sample",
                        "commercial": "sample"}}},
            "cost unit conversions": {
                "whole building": {
                    "wireless sensor network": {
                        "original units": "$/node",
                        "revised units": "$/ft^2 floor",
                        "conversion factor": {
                            "description": "sample",
                            "value": {
                                "residential": {
                                    "single family home": 0.0021,
                                    "mobile home": 0.0021,
                                    "multi family home": 0.0041},
                                "commercial": 0.002},
                            "units": "nodes/ft^2 floor",
                            "source": {
                                "residential": "sample",
                                "commercial": "sample"},
                            "notes": "sample"}},
                    "occupant-centered sensing and controls": {
                        "original units": "$/occupant",
                        "revised units": "$/ft^2 floor",
                        "conversion factor": {
                            "description": "sample",
                            "value": {
                                "residential": {
                                    "single family home": {
                                        "Single-Family": 0.001075},
                                    "mobile home": {
                                        "Single-Family": 0.001075},
                                    "multi family home": {
                                        "Multifamily": 0.00215}},
                                "commercial": {
                                    "assembly": {
                                        "Hospital": 0.005},
                                    "education": {
                                        "PrimarySchool": 0.02,
                                        "SecondarySchool": 0.02},
                                    "food sales": {
                                        "Supermarket": 0.008},
                                    "food service": {
                                        "QuickServiceRestaurant": 0.07,
                                        "FullServiceRestaurant": 0.07},
                                    "health care": 0.005,
                                    "lodging": {
                                        "SmallHotel": 0.005,
                                        "LargeHotel": 0.005},
                                    "large office": {
                                        "LargeOffice": 0.005,
                                        "MediumOffice": 0.005},
                                    "small office": {
                                        "SmallOffice": 0.005,
                                        "OutpatientHealthcare": 0.02},
                                    "mercantile/service": {
                                        "RetailStandalone": 0.01,
                                        "RetailStripmall": 0.01},
                                    "warehouse": {
                                        "Warehouse": 0.0001},
                                    "other": 0.005}},
                            "units": "occupants/ft^2 floor",
                            "source": {
                                "residential": "sample",
                                "commercial": "sample"},
                            "notes": ""}}},
                "heating and cooling": {
                    "supply": {
                        "heating equipment": {
                            "original units": "$/kBtu/h heating",
                            "revised units": "$/ft^2 floor",
                            "conversion factor": {
                                "description": "sample",
                                "value": 0.020,
                                "units": "kBtu/h heating/ft^2 floor",
                                "source": "Rule of thumb",
                                "notes": "sample"}},
                        "cooling equipment": {
                            "original units": "$/kBtu/h cooling",
                            "revised units": "$/ft^2 floor",
                            "conversion factor": {
                                "description": "sample",
                                "value": 0.036,
                                "units": "kBtu/h cooling/ft^2 floor",
                                "source": "Rule of thumb",
                                "notes": "sample"}}},
                    "demand": {
                        "windows": {
                            "original units": "$/ft^2 glazing",
                            "revised units": "$/ft^2 wall",
                            "conversion factor": {
                                "description": "Window to wall ratio",
                                "value": {
                                    "residential": {
                                        "single family home": {
                                            "Single-Family": 0.15},
                                        "mobile home": {
                                            "Single-Family": 0.15},
                                        "multi family home": {
                                            "Multifamily": 0.10}},
                                    "commercial": {
                                        "assembly": {
                                            "Hospital": 0.15},
                                        "education": {
                                            "PrimarySchool": 0.35,
                                            "SecondarySchool": 0.33},
                                        "food sales": {
                                            "Supermarket": 0.11},
                                        "food service": {
                                            "QuickServiceRestaurant": 0.14,
                                            "FullServiceRestaurant": 0.17},
                                        "health care": 0.2,
                                        "lodging": {
                                            "SmallHotel": 0.11,
                                            "LargeHotel": 0.27},
                                        "large office": {
                                            "LargeOffice": 0.38,
                                            "MediumOffice": 0.33},
                                        "small office": {
                                            "SmallOffice": 0.21,
                                            "OutpatientHealthcare": 0.19},
                                        "mercantile/service": {
                                            "RetailStandalone": 0.07,
                                            "RetailStripmall": 0.11},
                                        "warehouse": {
                                            "Warehouse": 0.006},
                                        "other": 0.2}},
                                "units": None,
                                "source": {
                                    "residential": "sample",
                                    "commercial": "sample"},
                                "notes": "sample"}},
                        "walls": {
                            "original units": "$/ft^2 wall",
                            "revised units": "$/ft^2 floor",
                            "conversion factor": {
                                "description": "Wall to floor ratio",
                                "value": {
                                    "residential": {
                                        "single family home": {
                                            "Single-Family": 1},
                                        "mobile home": {
                                            "Single-Family": 1},
                                        "multi family home": {
                                            "Multifamily": 1}},
                                    "commercial": {
                                        "assembly": {
                                            "Hospital": 0.26},
                                        "education": {
                                            "PrimarySchool": 0.20,
                                            "SecondarySchool": 0.16},
                                        "food sales": {
                                            "Supermarket": 0.38},
                                        "food service": {
                                            "QuickServiceRestaurant": 0.80,
                                            "FullServiceRestaurant": 0.54},
                                        "health care": 0.4,
                                        "lodging": {
                                            "SmallHotel": 0.40,
                                            "LargeHotel": 0.38},
                                        "large office": {
                                            "LargeOffice": 0.26,
                                            "MediumOffice": 0.40},
                                        "small office": {
                                            "SmallOffice": 0.55,
                                            "OutpatientHealthcare": 0.35},
                                        "mercantile/service": {
                                            "RetailStandalone": 0.51,
                                            "RetailStripmall": 0.57},
                                        "warehouse": {
                                            "Warehouse": 0.53},
                                        "other": 0.4}},
                                "units": None,
                                "source": {
                                    "residential": "sample",
                                    "commercial": "sample"},
                                "notes": "sample"}},
                        "footprint": {
                            "original units": "$/ft^2 footprint",
                            "revised units": "$/ft^2 floor",
                            "conversion factor": {
                                "description": "sample",
                                "value": {
                                    "residential": {
                                        "single family home": {
                                            "Single-Family": 0.5},
                                        "mobile home": {
                                            "Single-Family": 0.5},
                                        "multi family home": {
                                            "Multifamily": 0.33}},
                                    "commercial": {
                                        "assembly": {
                                            "Hospital": 0.20},
                                        "education": {
                                            "PrimarySchool": 1,
                                            "SecondarySchool": 0.5},
                                        "food sales": {"Supermarket": 1},
                                        "food service": {
                                            "QuickServiceRestaurant": 1,
                                            "FullServiceRestaurant": 1},
                                        "health care": 0.2,
                                        "lodging": {
                                            "SmallHotel": 0.25,
                                            "LargeHotel": 0.17},
                                        "large office": {
                                            "LargeOffice": 0.083,
                                            "MediumOffice": 0.33},
                                        "small office": {
                                            "SmallOffice": 1,
                                            "OutpatientHealthcare": 0.33},
                                        "mercantile/service": {
                                            "RetailStandalone": 1,
                                            "RetailStripmall": 1},
                                        "warehouse": {
                                            "Warehouse": 1},
                                        "other": 1}},
                                "units": None,
                                "source": {
                                    "residential": "sample",
                                    "commercial": "sample"},
                                "notes": "sample"}},
                        "roof": {
                            "original units": "$/ft^2 roof",
                            "revised units": "$/ft^2 footprint",
                            "conversion factor": {
                                "description": "sample",
                                "value": {
                                    "residential": 1.05,
                                    "commercial": 1},
                                "units": None,
                                "source": "Rule of thumb",
                                "notes": "sample"}}}},
                "ventilation": {
                    "original units": "$/1000 CFM",
                    "revised units": "$/ft^2 floor",
                    "conversion factor": {
                        "description": "sample",
                        "value": 0.001,
                        "units": "1000 CFM/ft^2 floor",
                        "source": "Rule of thumb",
                        "notes": "sample"}},
                "lighting": {
                    "original units": "$/1000 lm",
                    "revised units": "$/ft^2 floor",
                    "conversion factor": {
                        "description": "sample",
                        "value": 0.049,
                        "units": "1000 lm/ft^2 floor",
                        "source": "sample",
                        "notes": "sample"}},
                "water heating": {
                    "original units": "$/kBtu/h water heating",
                    "revised units": "$/ft^2 floor",
                    "conversion factor": {
                        "description": "sample",
                        "value": 0.012,
                        "units": "kBtu/h water heating/ft^2 floor",
                        "source": "sample",
                        "notes": "sample"}},
                "refrigeration": {
                    "original units": "$/kBtu/h refrigeration",
                    "revised units": "$/ft^2 floor",
                    "conversion factor": {
                        "description": "sample",
                        "value": 0.02,
                        "units": "kBtu/h refrigeration/ft^2 floor",
                        "source": "sample",
                        "notes": "sample"}},
                "cooking": {},
                "MELs": {}
            }
        }
        cls.sample_bldgsect_ok_in = [
            "residential", "commercial", "commercial", "commercial",
            "commercial", "commercial", "commercial", "commercial",
            "residential", "residential", "commercial", "residential",
            "residential"]
        cls.sample_mskeys_ok_in = [
            ('primary', 'marine', 'single family home', 'electricity',
             'cooling', 'demand', 'windows conduction', 'existing'),
            ('primary', 'marine', 'assembly', 'electricity', 'heating',
             'supply', 'rooftop_ASHP-heat', 'new'),
            ('primary', 'marine', 'food sales', 'electricity', 'cooling',
             'demand', 'ground', 'new'),
            ('primary', 'marine', 'education', 'electricity', 'cooling',
             'demand', 'roof', 'existing'),
            ('primary', 'marine', 'lodging', 'electricity', 'cooling',
             'demand', 'wall', 'new'),
            ('primary', 'marine', 'food service', 'electricity', 'ventilation',
             'CAV_Vent', 'existing'),
            ('primary', 'marine', 'small office', 'electricity', 'cooling',
             'reciprocating_chiller', 'existing'),
            ('primary', 'mixed humid', 'health care', 'electricity', 'cooling',
             'demand', 'roof', 'existing'),
            ('primary', 'mixed humid', 'single family home', 'electricity',
             'cooling', 'supply', 'ASHP'),
            ('primary', 'mixed humid', 'single family home', 'electricity',
             'lighting', 'linear fluorescent (LED)'),
            ('primary', 'marine', 'food service', 'electricity', 'ventilation',
             'CAV_Vent', 'existing'),
            ('primary', 'mixed humid', 'multi family home', 'electricity',
             'lighting', 'general service (CFL)'),
            ('primary', 'mixed humid', 'multi family home', 'electricity',
             'lighting', 'general service (CFL)')]
        cls.sample_mskeys_fail_in = [
            ('primary', 'marine', 'single family home', 'electricity',
             'cooling', 'demand', 'windows conduction', 'existing'),
            ('primary', 'marine', 'assembly', 'electricity', 'PCs',
             None, 'new'),
            ('primary', 'marine', 'single family home', 'electricity', 'PCs',
             None, 'new')]
        cls.cost_meas_ok_in = 10
        cls.cost_meas_units_ok_in_yronly = '2008$/ft^2 floor'
        cls.cost_meas_units_ok_in_all = [
            '$/ft^2 glazing', '2013$/kBtu/h heating', '2010$/ft^2 footprint',
            '2016$/ft^2 roof', '2013$/ft^2 wall', '2012$/1000 CFM',
            '2013$/occupant', '2013$/ft^2 roof', '2013$/node',
            '2013$/ft^2 floor', '2013$/node', '2013$/node',
            '2013$/occupant']
        cls.cost_meas_units_fail_in = [
            '$/ft^2 facade', '$/kWh', '$/ft^2 floor']
        cls.cost_base_units_fail_in = [
            '2013$/ft^2 floor', '2013$/ft^2 floor', '2013$/unit']
        cls.cost_base_units_ok_in = numpy.repeat('2013$/ft^2 floor', 13)
        cls.ok_out_costs_yronly = 11.11
        cls.ok_out_costs_all = [
            1.47, 0.2, 10.65, 6.18, 3.85, 0.01015, 0.182,
            2, 0.021, 10, 0.02, 0.041, 0.0215]

    def test_convertcost_ok_yronly(self):
        """Test 'convert_costs' function for year only conversion."""
        func_output = self.sample_measure_in.convert_costs(
            self.sample_convertdata_ok_in, self.sample_bldgsect_ok_in[0],
            self.sample_mskeys_ok_in[0], self.cost_meas_ok_in,
            self.cost_meas_units_ok_in_yronly,
            self.cost_base_units_ok_in[0], self.verbose)
        numpy.testing.assert_almost_equal(
            func_output[0], self.ok_out_costs_yronly, decimal=2)
        self.assertEqual(func_output[1], self.cost_base_units_ok_in[0])

    def test_convertcost_ok_all(self):
        """Test 'convert_costs' function for year/units conversion."""
        for k in range(0, len(self.sample_mskeys_ok_in)):
            func_output = self.sample_measure_in.convert_costs(
                self.sample_convertdata_ok_in, self.sample_bldgsect_ok_in[k],
                self.sample_mskeys_ok_in[k], self.cost_meas_ok_in,
                self.cost_meas_units_ok_in_all[k],
                self.cost_base_units_ok_in[k], self.verbose)
            numpy.testing.assert_almost_equal(
                func_output[0], self.ok_out_costs_all[k], decimal=2)
            self.assertEqual(
                func_output[1], self.cost_base_units_ok_in[k])

    def test_convertcost_fail(self):
        """Test 'convert_costs' function given invalid inputs."""
        for k in range(0, len(self.sample_mskeys_fail_in)):
            with self.assertRaises(KeyError):
                self.sample_measure_in.convert_costs(
                    self.sample_convertdata_ok_in,
                    self.sample_bldgsect_ok_in[k],
                    self.sample_mskeys_fail_in[k], self.cost_meas_ok_in,
                    self.cost_meas_units_fail_in[k],
                    self.cost_base_units_fail_in[k], self.verbose)


class UpdateMeasuresTest(unittest.TestCase, CommonMethods):
    """Test 'prepare_measures' function.

    Ensure that function properly instantiates Measure objects and finalizes
    attributes for these objects.

    Attributes:
        handyvars (object): Global variables to use across measures.
        verbose (NoneType): Determines whether to print all user messages.
        tsv_data (dict): Sample time-varying load, price, and emissions data.
        cbecs_sf_byvint (dict): Commercial square footage by vintage data.
        sample_mseg_in (dict): Sample baseline microsegment stock/energy.
        sample_cpl_in (dict): Sample baseline technology cost, performance,
            and lifetime.
        measures_ok_in (list): List of measures with valid user-defined
            'status' attributes.
        measures_warn_in (list): List of measures that includes one measure
            with invalid 'status' attribute (the measure's 'markets' attribute
            has not been finalized but user has not flagged it for an update).
        convert_data (dict): Data used to convert expected
            user-defined measure cost units to cost units required by Scout
            analysis engine.
        ok_out (list): List of measure master microsegment dicts that
            should be generated by 'prepare_measures' given sample input
            measure information to update and an assumed technical potential
            adoption scenario.
        ok_warnmeas_out (list): Warnings that should be yielded when running
            'measures_warn_in' through the function.
    """

    @classmethod
    def setUpClass(cls):
        """Define variables and objects for use across all class functions."""
        # Base directory
        cls.base_dir = os.getcwd()
        cls.handyvars = ecm_prep.UsefulVars(cls.base_dir,
                                            ecm_prep.UsefulInputFiles())
        # Hard code aeo_years to fit test years
        cls.handyvars.aeo_years = ["2009", "2010"]
        cls.cbecs_sf_byvint = {
            '2004 to 2007': 6524.0, '1960 to 1969': 10362.0,
            '1946 to 1959': 7381.0, '1970 to 1979': 10846.0,
            '1990 to 1999': 13803.0, '2000 to 2003': 7215.0,
            'Before 1920': 3980.0, '2008 to 2012': 5726.0,
            '1920 to 1945': 6020.0, '1980 to 1989': 15185.0}
        # Hard code carbon intensity, site-source conversion, and cost data for
        # tests such that these data are not dependent on an input file that
        # may change in the future
        cls.handyvars.ss_conv = {
            "electricity": {"2009": 3.19, "2010": 3.20},
            "natural gas": {"2009": 1.01, "2010": 1.01},
            "distillate": {"2009": 1.01, "2010": 1.01},
            "other fuel": {"2009": 1.01, "2010": 1.01}}
        cls.handyvars.carb_int = {
            "residential": {
                "electricity": {"2009": 56.84702689, "2010": 56.16823191},
                "natural gas": {"2009": 56.51576602, "2010": 54.91762852},
                "distillate": {"2009": 49.5454521, "2010": 52.59751597},
                "other fuel": {"2009": 49.5454521, "2010": 52.59751597}},
            "commercial": {
                "electricity": {"2009": 56.84702689, "2010": 56.16823191},
                "natural gas": {"2009": 56.51576602, "2010": 54.91762852},
                "distillate": {"2009": 49.5454521, "2010": 52.59751597},
                "other fuel": {"2009": 49.5454521, "2010": 52.59751597}}}
        cls.handyvars.ecosts = {
            "residential": {
                "electricity": {"2009": 10.14, "2010": 9.67},
                "natural gas": {"2009": 11.28, "2010": 10.78},
                "distillate": {"2009": 21.23, "2010": 20.59},
                "other fuel": {"2009": 21.23, "2010": 20.59}},
            "commercial": {
                "electricity": {"2009": 9.08, "2010": 8.55},
                "natural gas": {"2009": 8.96, "2010": 8.59},
                "distillate": {"2009": 14.81, "2010": 14.87},
                "other fuel": {"2009": 14.81, "2010": 14.87}}}
        cls.handyvars.ccosts = {"2009": 33, "2010": 33}
        cls.verbose = None
        cls.tsv_data = {
            "load": {
              "AIA_CZ1": {
                "residential": {
                  "heating": {
                    "winter": {
                      "months": [
                        1,
                        2,
                        12
                      ],
                      "annual_days": 90,
                      "fractions": {
                        "weekday": [
                          0.012202256455352733,
                          0.012202256455352733,
                          0.012790369837445772,
                          0.01354335327206579,
                          0.014412162613847488,
                          0.015259279121150411,
                          0.015853297848280774,
                          0.015928471021456836,
                          0.015332968218593672,
                          0.014155976960109057,
                          0.012669478965647952,
                          0.011162898928851443,
                          0.009864588218574728,
                          0.008928691840308131,
                          0.008419616601380887,
                          0.008337276785137526,
                          0.008657777623759138,
                          0.009295666950390356,
                          0.010056738183651286,
                          0.010714075913172366,
                          0.011132857599974094,
                          0.01131327739593043,
                          0.011359135633914552,
                          0.011432694001907577
                        ],
                        "weekend": [
                          0.005241914064820976,
                          0.005241914064820976,
                          0.005479964558914669,
                          0.005766692417852683,
                          0.006121364449071813,
                          0.006531657677672043,
                          0.006924303274533763,
                          0.007151601035392774,
                          0.007047308555582134,
                          0.006554883454248733,
                          0.005797373314887126,
                          0.004993297019974449,
                          0.004324320580840767,
                          0.003874842240940412,
                          0.003646836954407323,
                          0.0036070550958290726,
                          0.0037213635750740865,
                          0.00395311415662022,
                          0.0042500266143626715,
                          0.004552908776331854,
                          0.004815668602839308,
                          0.005012872039222633,
                          0.00513509652610582,
                          0.005182074671008964
                        ]
                      }
                    },
                    "summer": {
                      "months": [
                        5,
                        6,
                        7,
                        8,
                        9
                      ],
                      "annual_days": 153,
                      "fractions": {
                        "weekday": [
                          0.0010590636426289091,
                          0.0010590636426289091,
                          0.001094523946095479,
                          0.0011479534348979225,
                          0.0012135479343554246,
                          0.0012775786485038569,
                          0.001316407844730775,
                          0.0013019566152529193,
                          0.0012199040244830553,
                          0.0010880214351182012,
                          0.0009479778372020717,
                          0.0008349335540973944,
                          0.0007598879766524797,
                          0.0007167523336559638,
                          0.0006985608004971985,
                          0.0007058953734481931,
                          0.0007411524747124881,
                          0.0007972762496801779,
                          0.0008575041127562266,
                          0.0009071925861580299,
                          0.0009419989359581119,
                          0.0009663272187837232,
                          0.0009884582999645222,
                          0.0010172826848597876
                        ],
                        "weekend": [
                          0.0004817841819163308,
                          0.0004817841819163308,
                          0.0005027855713473914,
                          0.0005286093783583508,
                          0.0005565142687933293,
                          0.0005841833554293074,
                          0.0006075787234184459,
                          0.000618502357523313,
                          0.0006058653602035742,
                          0.0005638157685378343,
                          0.00049960965014296,
                          0.00043034690944955496,
                          0.00037199075437145007,
                          0.000332194578928617,
                          0.0003108630908884448,
                          0.00030421774349246824,
                          0.00030762615314860656,
                          0.00031711380102401697,
                          0.00033072136392778284,
                          0.0003482878625037381,
                          0.00036938031048864233,
                          0.0003915214454442425,
                          0.00040977858976023237,
                          0.0004171754859352801
                        ]
                      }
                    },
                    "intermediate": {
                      "months": [
                        10,
                        11,
                        3,
                        4
                      ],
                      "annual_days": 122,
                      "fractions": {
                        "weekday": [
                          0.016540836528367037,
                          0.016540836528367037,
                          0.017338056890759825,
                          0.018358767768800296,
                          0.01953648709877104,
                          0.020684800586448338,
                          0.02149002597211394,
                          0.02159192738464149,
                          0.02078469025187142,
                          0.01918921321259228,
                          0.017174182597878333,
                          0.015131929659109733,
                          0.013371997362956857,
                          0.012103337827973246,
                          0.011413258059649647,
                          0.011301641864297534,
                          0.01173609855665128,
                          0.012600792977195817,
                          0.01363246731561619,
                          0.014523525126744765,
                          0.015091206968853771,
                          0.015335776025594586,
                          0.01539793941486195,
                          0.015497651869252492
                        ],
                        "weekend": [
                          0.007105705732312879,
                          0.007105705732312879,
                          0.0074283964020843305,
                          0.007817071944200307,
                          0.008297849586519569,
                          0.008854024851955437,
                          0.009386277772145768,
                          0.00969439251464354,
                          0.00955301826423356,
                          0.008885508682426062,
                          0.00785866160462477,
                          0.0067686915159653645,
                          0.005861856787361929,
                          0.005252563926608114,
                          0.0049434900937521484,
                          0.004889563574346076,
                          0.0050445150684337615,
                          0.005358665856751855,
                          0.005761147188358289,
                          0.006171720785694292,
                          0.006527906328293286,
                          0.006795226542057347,
                          0.006960908624276779,
                          0.007024590109589927
                        ]
                      }
                    }
                  },
                  "cooling": {
                    "winter": {
                      "months": [
                        1,
                        2,
                        12
                      ],
                      "annual_days": 90,
                      "fractions": {
                        "weekday": [
                          0.00029388695616978906,
                          0.00029388695616978906,
                          0.0002272911239088048,
                          0.0001862752788241577,
                          0.00016366394068718788,
                          0.00015345765257191167,
                          0.00015204597235863684,
                          0.00015930601383760677,
                          0.00017839530716971818,
                          0.0002138646323280441,
                          0.0002700160616097575,
                          0.00035025438210998925,
                          0.0004550485160393275,
                          0.0005788167876161717,
                          0.0007087420314413435,
                          0.0008249179903766019,
                          0.000902147642474604,
                          0.000919763959698822,
                          0.0008757603039163335,
                          0.0007879516022946396,
                          0.0006811311900149874,
                          0.0005758465473089568,
                          0.0004853777281694694,
                          0.000417210396139057
                        ],
                        "weekend": [
                          0.00017198724621535864,
                          0.00017198724621535864,
                          0.0001448203226654988,
                          0.00012430459765636404,
                          0.00010962872727193139,
                          0.00010032155133870697,
                          9.675559574179694e-05,
                          0.0001006950819154731,
                          0.00011527100727456558,
                          0.0001438039321707539,
                          0.00018808298936304126,
                          0.00024721733935680393,
                          0.0003172369055665132,
                          0.00039166578409408455,
                          0.00046282408177673244,
                          0.0005219832028562106,
                          0.0005589542804663337,
                          0.0005654913037505377,
                          0.0005413065164472199,
                          0.0004945543965493874,
                          0.00043616247179917625,
                          0.0003750154635123981,
                          0.00031682778933344994,
                          0.0002649468311053816
                        ]
                      }
                    },
                    "summer": {
                      "months": [
                        5,
                        6,
                        7,
                        8,
                        9
                      ],
                      "annual_days": 153,
                      "fractions": {
                        "weekday": [
                          0.0178088887958826,
                          0.0178088887958826,
                          0.014536854461312478,
                          0.01227834761570038,
                          0.010855986007362237,
                          0.01012533621858267,
                          0.010014340354937873,
                          0.010565668182555539,
                          0.011946601116842035,
                          0.01439426977798482,
                          0.018117069323786088,
                          0.023182300524433597,
                          0.029401334959849496,
                          0.03629853484339642,
                          0.04319544884521712,
                          0.0492252062720987,
                          0.0532917583536315,
                          0.05441884594599187,
                          0.05242354274540074,
                          0.048053564600871124,
                          0.042430182138863994,
                          0.03651397256114906,
                          0.03094469115389148,
                          0.026101788619276922
                        ],
                        "weekend": [
                          0.007192612245437178,
                          0.007192612245437178,
                          0.005896374300210337,
                          0.00500025925774603,
                          0.00441780603466515,
                          0.004084926818068662,
                          0.003993932570955657,
                          0.004221738764403182,
                          0.004908787278297272,
                          0.006174856157130429,
                          0.008050458669069673,
                          0.010476732191630676,
                          0.013305527379358343,
                          0.01628373850668657,
                          0.019083559062004343,
                          0.021345222778859585,
                          0.022693136070019188,
                          0.022838103003205577,
                          0.021769641978571088,
                          0.019791106527092022,
                          0.017341365539618115,
                          0.014819949432887782,
                          0.012528892232201546,
                          0.010686532395010731
                        ]
                      }
                    },
                    "intermediate": {
                      "months": [
                        10,
                        11,
                        3,
                        4
                      ],
                      "annual_days": 122,
                      "fractions": {
                        "weekday": [
                          0.00039838009614126963,
                          0.00039838009614126963,
                          0.00030810574574304656,
                          0.0002525064890727471,
                          0.00022185556404263253,
                          0.0002080203734863692,
                          0.00020610676253059662,
                          0.00021594815209097812,
                          0.00024182474971895133,
                          0.00028990539048912646,
                          0.000366021772404338,
                          0.0004747892735268743,
                          0.0006168435439644217,
                          0.0007846183121019218,
                          0.0009607391981760436,
                          0.0011182221647327271,
                          0.0012229112486877966,
                          0.0012467911453695145,
                          0.0011871417453088078,
                          0.0010681121719994004,
                          0.000923311168686983,
                          0.0007805919863521416,
                          0.0006579564759630585,
                          0.0005655518703218328
                        ],
                        "weekend": [
                          0.00023313826709193063,
                          0.00023313826709193063,
                          0.00019631199294656504,
                          0.00016850178793418236,
                          0.00014860783030195144,
                          0.0001359914362591361,
                          0.0001311575853388803,
                          0.00013649777770764133,
                          0.00015625625430552224,
                          0.00019493421916479977,
                          0.00025495694113656704,
                          0.00033511683779477864,
                          0.00043003224976794017,
                          0.000530924729549759,
                          0.0006273837552973484,
                          0.0007075772305384189,
                          0.0007576935801876968,
                          0.0007665548784173957,
                          0.0007337710556284536,
                          0.0006703959597669474,
                          0.0005912424617722168,
                          0.0005083542949834729,
                          0.0004294776699853433,
                          0.00035915014883173955
                        ]
                      }
                    }
                  }}},
              "AIA_CZ2": {
                "residential": {
                  "heating": {
                    "winter": {
                      "months": [
                        1,
                        2,
                        12
                      ],
                      "annual_days": 90,
                      "fractions": {
                        "weekday": [
                          0.012328325644744146,
                          0.012328325644744146,
                          0.01292944656564235,
                          0.013696112711290006,
                          0.01457856924649585,
                          0.015433740380703598,
                          0.016017408874061726,
                          0.016047648811339597,
                          0.015368664270279565,
                          0.014093632635079652,
                          0.012535759134544862,
                          0.01100932986990283,
                          0.009733726578093594,
                          0.00883583942118992,
                          0.008360675389510937,
                          0.00830484348500009,
                          0.008646190980309455,
                          0.009297762070867558,
                          0.010065459149265247,
                          0.010728761483143417,
                          0.011161292725380368,
                          0.0113678676013609,
                          0.011451361161904944,
                          0.011568794765278995
                        ],
                        "weekend": [
                          0.005309212872748672,
                          0.005309212872748672,
                          0.005535713662746949,
                          0.005819632025359939,
                          0.006173004111628854,
                          0.00657859563517025,
                          0.006960950428698515,
                          0.007172643098210336,
                          0.00704910659251082,
                          0.006536142805715583,
                          0.005760272913918485,
                          0.004944107710216288,
                          0.004270995106846551,
                          0.003822662209656965,
                          0.003596565738074613,
                          0.0035568366162615403,
                          0.0036689782568839853,
                          0.0038967600961714983,
                          0.004189315911028903,
                          0.004490352702852043,
                          0.004756708902044259,
                          0.004963925299846759,
                          0.005100741803816752,
                          0.005162409674321511
                        ]
                      }
                    },
                    "summer": {
                      "months": [
                        5,
                        6,
                        7,
                        8,
                        9
                      ],
                      "annual_days": 153,
                      "fractions": {
                        "weekday": [
                          0.00104208660061774,
                          0.00104208660061774,
                          0.0010793761693862892,
                          0.0011334748067871325,
                          0.0011988531851171644,
                          0.0012623933066180319,
                          0.0013012147155246098,
                          0.0012876916720357737,
                          0.0012071835346915583,
                          0.0010765459246448881,
                          0.0009368239329836688,
                          0.0008233559084441718,
                          0.0007477585231276835,
                          0.0007044649892616131,
                          0.0006866281956131476,
                          0.0006943939408031098,
                          0.0007294438986384539,
                          0.0007845316662159281,
                          0.0008435761379043598,
                          0.000892712631247282,
                          0.0009275611431055113,
                          0.0009515116563989013,
                          0.0009711837608622172,
                          0.0009935036040558429
                        ],
                        "weekend": [
                          0.0004373638853776625,
                          0.0004373638853776625,
                          0.0004555421334352469,
                          0.0004786211919526792,
                          0.0005038898992500097,
                          0.0005291146366347936,
                          0.0005506635838727076,
                          0.0005612619807500183,
                          0.0005508889132636936,
                          0.000513860577238207,
                          0.0004561561638926308,
                          0.000393070015658586,
                          0.00033949378758980437,
                          0.00030294053307570345,
                          0.0002834657987607928,
                          0.0002773465723638926,
                          0.00028012957996336287,
                          0.00028828849734042713,
                          0.00030024250648906465,
                          0.0003158838022720821,
                          0.0003347228693727044,
                          0.00035443589722291207,
                          0.0003705665841250921,
                          0.00037688845230795837
                        ]
                      }
                    },
                    "intermediate": {
                      "months": [
                        10,
                        11,
                        3,
                        4
                      ],
                      "annual_days": 122,
                      "fractions": {
                        "weekday": [
                          0.016711730318430956,
                          0.016711730318430956,
                          0.017526583122315188,
                          0.018565841675304232,
                          0.019762060534138818,
                          0.02092129251606488,
                          0.021712487584839235,
                          0.0217534794998159,
                          0.020833078233045636,
                          0.01910470201644131,
                          0.01699291793793859,
                          0.014923758268090507,
                          0.013194607139193541,
                          0.01197747121539078,
                          0.011333359972448161,
                          0.011257676724111232,
                          0.011720392217752819,
                          0.012603633029398245,
                          0.013644289069004003,
                          0.014543432232705523,
                          0.015129752361071166,
                          0.01540977608184478,
                          0.015522956241693371,
                          0.015682144015155976
                        ],
                        "weekend": [
                          0.007196933005281533,
                          0.007196933005281533,
                          0.00750396740950142,
                          0.007888834523265695,
                          0.00836785001798578,
                          0.008917651861008562,
                          0.009435955025569097,
                          0.009722916199796233,
                          0.009555455603181336,
                          0.008860104692192235,
                          0.00780836994997839,
                          0.006702012673848746,
                          0.005789571144836436,
                          0.005181830995312775,
                          0.004875344667167809,
                          0.004821489635376755,
                          0.004973503859331625,
                          0.005282274797032475,
                          0.005678850457172513,
                          0.006086922552754993,
                          0.0064479831783266625,
                          0.006728876517570051,
                          0.006914338889618264,
                          0.006997933114080271
                        ]
                      }
                    }
                  },
                  "cooling": {
                    "winter": {
                      "months": [
                        1,
                        2,
                        12
                      ],
                      "annual_days": 90,
                      "fractions": {
                        "weekday": [
                          0.0005300091336117748,
                          0.0005300091336117748,
                          0.0004221795216523343,
                          0.00035196890617842573,
                          0.0003103591636854973,
                          0.0002899940288915328,
                          0.00028648383970524764,
                          0.00029978137777895514,
                          0.0003346316221272169,
                          0.00039917492732269804,
                          0.0005020539198869063,
                          0.0006484175467390152,
                          0.0008351713983307837,
                          0.0010488319213534565,
                          0.0012675355776307527,
                          0.0014614414579304461,
                          0.0015923500937396271,
                          0.0016271131808821761,
                          0.0015609580794978743,
                          0.0014208088023084672,
                          0.0012448867282422982,
                          0.001064243586781173,
                          0.0008977442807991897,
                          0.0007545969564686696
                        ],
                        "weekend": [
                          0.00017181268912529635,
                          0.00017181268912529635,
                          0.00014767002645267794,
                          0.00012826647934427468,
                          0.0001140013970314869,
                          0.00010517245543939914,
                          0.00010236644309561494,
                          0.0001070305005186204,
                          0.00012184881018502623,
                          0.0001502837476230197,
                          0.00019517461480859943,
                          0.00025699294771985273,
                          0.00033242141555419794,
                          0.0004142956381487231,
                          0.0004931385048222993,
                          0.000558197467494742,
                          0.0005978071718920404,
                          0.0006030992716937094,
                          0.0005740800297508947,
                          0.0005200538644268434,
                          0.0004537447295639849,
                          0.00038623655465746165,
                          0.0003256841054095974,
                          0.0002780339885941499
                        ]
                      }
                    },
                    "summer": {
                      "months": [
                        5,
                        6,
                        7,
                        8,
                        9
                      ],
                      "annual_days": 153,
                      "fractions": {
                        "weekday": [
                          0.017453347080087375,
                          0.017453347080087375,
                          0.014318337364974908,
                          0.01213526118783814,
                          0.010747227329010864,
                          0.010029641128642573,
                          0.009930216634337824,
                          0.010509938311424926,
                          0.011946902362372102,
                          0.014473048633380623,
                          0.018273678292171677,
                          0.02338301188450458,
                          0.029580170841633894,
                          0.036368814782070984,
                          0.04307383358551025,
                          0.04886651672165595,
                          0.05271814236195521,
                          0.05371313471475342,
                          0.05168204216580169,
                          0.04734089291228339,
                          0.04177022051567407,
                          0.03590688108643249,
                          0.03038762231836138,
                          0.025603423648539708
                        ],
                        "weekend": [
                          0.006783345569545233,
                          0.006783345569545233,
                          0.005541638314082507,
                          0.004695076942793867,
                          0.004152845071093804,
                          0.0038475896970159647,
                          0.003769707731771681,
                          0.00399468972335188,
                          0.004659680066909567,
                          0.005878016853924299,
                          0.0076742572954088765,
                          0.009989974306203029,
                          0.012684765744682063,
                          0.01551579984171551,
                          0.018165264162198307,
                          0.02028784441423032,
                          0.021531226386438576,
                          0.021628829698162974,
                          0.020575465296081348,
                          0.018660942164656864,
                          0.01630532786692724,
                          0.013894767901503978,
                          0.011724989138890416,
                          0.010012581807600826
                        ]
                      }
                    },
                    "intermediate": {
                      "months": [
                        10,
                        11,
                        3,
                        4
                      ],
                      "annual_days": 122,
                      "fractions": {
                        "weekday": [
                          0.0007184568255626282,
                          0.0007184568255626282,
                          0.0005722877960176088,
                          0.0004771134061529771,
                          0.00042070908855145194,
                          0.00039310301694185564,
                          0.0003883447604893357,
                          0.00040637031210036153,
                          0.0004536117544391163,
                          0.0005411037903707685,
                          0.0006805619802911397,
                          0.0008789660078017763,
                          0.0011321212288483958,
                          0.001421749937834686,
                          0.0017182148941216873,
                          0.0019810650874168274,
                          0.0021585190159581612,
                          0.0022056423118625057,
                          0.0021159653966526743,
                          0.0019259852653514783,
                          0.0016875131205062266,
                          0.0014426413065255902,
                          0.0012169422473055683,
                          0.001022898096546419
                        ],
                        "weekend": [
                          0.0002329016452587351,
                          0.0002329016452587351,
                          0.00020017492474696342,
                          0.00017387233866668342,
                          0.00015453522708712671,
                          0.00014256710626229664,
                          0.0001387634006407225,
                          0.00014508578959190766,
                          0.0001651728315841467,
                          0.00020371796900009337,
                          0.00026457003340721254,
                          0.00034836821802024487,
                          0.00045061569664013503,
                          0.0005616007539349358,
                          0.000668476639870228,
                          0.0007566676781595393,
                          0.0008103608330092104,
                          0.0008175345682959171,
                          0.0007781973736623241,
                          0.0007049619051119432,
                          0.0006150761889645129,
                          0.0005235651074245592,
                          0.0004414828984441209,
                          0.00037689051787207
                        ]
                      }
                    }
                  }}}},
            "price": {
              "AIA_CZ1": {
                "residential": {
                  "winter": {
                    "months": [
                      1,
                      2,
                      12
                    ],
                    "annual_days": 90.25,
                    "rates": {
                      "weekday": [
                        0.6562552797163391,
                        0.6562552797163391,
                        0.6562552797163391,
                        0.6562552797163391,
                        0.6562722224680656,
                        0.6578442485863384,
                        0.7235267658386892,
                        0.8409053866455017,
                        1.012563919002179,
                        1.217271077418888,
                        1.2125005556734563,
                        1.2057496380698587,
                        1.1988043072105958,
                        1.1826547505128486,
                        1.1833338836255691,
                        1.1835511313538214,
                        1.2407170480621692,
                        1.2770113386833148,
                        1.2766376843522398,
                        1.2525419733224212,
                        0.997037561299839,
                        0.7503122897528398,
                        0.6824694705086938,
                        0.6728076562529395
                      ],
                      "weekend": [
                        0.6644122978887247,
                        0.6644122978887247,
                        0.6644122978887247,
                        0.6644122978887247,
                        0.6644122978887247,
                        0.665113732663588,
                        0.6738333378241788,
                        0.6976045234405559,
                        0.7073939270906661,
                        0.7071505858599368,
                        0.7065294988071219,
                        0.7063849706660476,
                        0.6894592001856883,
                        0.681247569162237,
                        0.6813266103046596,
                        0.6816697006818776,
                        0.7058360518456535,
                        0.7092645790001153,
                        0.7092918676319172,
                        0.7100055253846985,
                        0.7083692085692868,
                        0.699741815510325,
                        0.6763846942735929,
                        0.6743807072224638
                      ]
                    }
                  },
                  "summer": {
                    "months": [
                      5,
                      6,
                      7,
                      8,
                      9
                    ],
                    "annual_days": 153,
                    "rates": {
                      "weekday": [
                        0.6458245873740424,
                        0.6458245873740424,
                        0.6458245873740424,
                        0.6458245873740424,
                        0.6458245873740424,
                        0.6468994741735525,
                        0.6721704283419366,
                        0.7877528153346143,
                        0.9508403698379019,
                        1.218453626925188,
                        1.270531964130501,
                        1.2733827123523953,
                        1.4115085817189656,
                        1.4987952877758426,
                        1.5191561886103309,
                        1.5199249270082422,
                        1.6247504057906499,
                        1.6339418703545154,
                        1.6025160033698258,
                        1.3678843705031805,
                        1.0303149049834759,
                        0.7475568270923396,
                        0.6723258865801299,
                        0.6636779143465007
                      ],
                      "weekend": [
                        0.6534945611557802,
                        0.6534945611557802,
                        0.6534945611557802,
                        0.6534945611557802,
                        0.6534945611557802,
                        0.6542221029139391,
                        0.6621663178269653,
                        0.6796723657035797,
                        0.6892275843534218,
                        0.6890302919287634,
                        0.688594812154047,
                        0.6885055018323561,
                        0.6764007903284276,
                        0.6677141658845643,
                        0.6678930377629508,
                        0.6683674190022503,
                        0.6876227199936777,
                        0.6910965171473628,
                        0.6911239469667035,
                        0.690723663696209,
                        0.6872672314327727,
                        0.6849410388318566,
                        0.6645116515218538,
                        0.6634792797131637
                      ]
                    }
                  },
                  "intermediate": {
                    "months": [
                      10,
                      11,
                      3,
                      4
                    ],
                    "annual_days": 122,
                    "rates": {
                      "weekday": [
                        0.6562778441085866,
                        0.6562778441085866,
                        0.6562778441085866,
                        0.6562778441085866,
                        0.656279641853995,
                        0.6578447685953613,
                        0.705174669017633,
                        0.8286455185797903,
                        0.9995293595504565,
                        1.2047023639699554,
                        1.2127149443241592,
                        1.2059862624248205,
                        1.1996754637517355,
                        1.183527727165945,
                        1.184196410698559,
                        1.1851517809866334,
                        1.2638951596822328,
                        1.2879865402334234,
                        1.2872477149518382,
                        1.2566187789076564,
                        0.9871707759014134,
                        0.749295816267223,
                        0.6823792035508683,
                        0.6728309763973485
                      ],
                      "weekend": [
                        0.6644478260228615,
                        0.6644478260228615,
                        0.6644478260228615,
                        0.6644478260228615,
                        0.6644478260228615,
                        0.6651398435784992,
                        0.6737605831198047,
                        0.6854959315714353,
                        0.7008227999148096,
                        0.7005426165885539,
                        0.6999493829042236,
                        0.6997976349876648,
                        0.6894625284116876,
                        0.6812703115779266,
                        0.6814184511586658,
                        0.6817205786085438,
                        0.7059317555796673,
                        0.7092665306112451,
                        0.709274613329601,
                        0.7099917167610817,
                        0.7084051532773447,
                        0.699783289154462,
                        0.6763460541022601,
                        0.6744115729038507
                      ]
                    }
                  }
                },
                "commercial": {
                  "winter": {
                    "months": [
                      1,
                      2,
                      12
                    ],
                    "annual_days": 90.25,
                    "rates": {
                      "weekday": [
                        0.7205377764969411,
                        0.7205377764969411,
                        0.7205413338353452,
                        0.7205499086137372,
                        0.7205827476257217,
                        0.7206534903518366,
                        0.7428535758106363,
                        0.8003921514970507,
                        0.917806328499009,
                        1.2136745446820991,
                        1.1882156592468782,
                        1.1849713667006732,
                        1.17899643189409,
                        1.1784705199117274,
                        1.1781947300567381,
                        1.1782157555195445,
                        1.2165445223153428,
                        1.2763514302607766,
                        1.2757532512417125,
                        1.2415597681168078,
                        0.9780590763376096,
                        0.8107292342104534,
                        0.7400972246396254,
                        0.7205377764969411
                      ],
                      "weekend": [
                        0.7412161219824536,
                        0.7412161219824536,
                        0.7412161219824536,
                        0.7412161219824536,
                        0.7412161219824536,
                        0.7412478401753293,
                        0.7467732270209331,
                        0.7561435578620747,
                        0.7559166568283232,
                        0.7583443482253794,
                        0.7583335022990093,
                        0.7579333886760348,
                        0.7473677590798047,
                        0.7473689802556748,
                        0.7473976778886215,
                        0.7474318442656821,
                        0.7562169189597919,
                        0.7624451218729195,
                        0.7670861841244224,
                        0.7670925554767881,
                        0.7603242970947867,
                        0.7601178324466221,
                        0.743698930185894,
                        0.7412161219824536
                      ]
                    }
                  },
                  "summer": {
                    "months": [
                      5,
                      6,
                      7,
                      8,
                      9
                    ],
                    "annual_days": 153,
                    "rates": {
                      "weekday": [
                        0.7115796922700992,
                        0.7115796922700992,
                        0.7115796922700992,
                        0.7115796922700992,
                        0.7115796922700992,
                        0.7116016410560142,
                        0.7257011780679133,
                        0.7762423849231626,
                        0.9001021701197353,
                        1.2058686735328008,
                        1.237133921833585,
                        1.2364964889854737,
                        1.3103669663261985,
                        1.4540365800905397,
                        1.4549769203256,
                        1.45658286681849,
                        1.5092289868724638,
                        1.51546495486032,
                        1.374160621562411,
                        1.29914398905371,
                        0.9554244917313884,
                        0.8257425558107331,
                        0.7264866867531394,
                        0.7115796922700992
                      ],
                      "weekend": [
                        0.7295382641238173,
                        0.7295382641238173,
                        0.7295382641238173,
                        0.7295382641238173,
                        0.7295382641238173,
                        0.7295590979230683,
                        0.7359977075558998,
                        0.7440531069705892,
                        0.7586727245017822,
                        0.7647310835238869,
                        0.7647278814414719,
                        0.7644574097064895,
                        0.7569421376440743,
                        0.7584933318257066,
                        0.7585106300473792,
                        0.7585315599399002,
                        0.766319183090172,
                        0.7669193687972687,
                        0.7660759243529977,
                        0.7693510638748012,
                        0.7642703937573375,
                        0.7641835113303687,
                        0.7298548667201737,
                        0.7295382641238173
                      ]
                    }
                  },
                  "intermediate": {
                    "months": [
                      10,
                      11,
                      3,
                      4
                    ],
                    "annual_days": 122,
                    "rates": {
                      "weekday": [
                        0.7209954326211352,
                        0.7209954326211352,
                        0.7209981603563667,
                        0.7210017442420723,
                        0.7210160598744189,
                        0.7210721551269182,
                        0.7392430156709856,
                        0.7965994368219024,
                        0.9139410447944187,
                        1.196225286155943,
                        1.1861622674475183,
                        1.1829831087056009,
                        1.178006410860889,
                        1.1781344090715444,
                        1.1779713309008437,
                        1.1780726729801054,
                        1.231171088644311,
                        1.275229259474271,
                        1.2739867949892427,
                        1.2318195002854422,
                        0.9749694849457833,
                        0.8094868447595314,
                        0.7400036939544639,
                        0.7209954326211352
                      ],
                      "weekend": [
                        0.7416487904590888,
                        0.7416487904590888,
                        0.7416487904590888,
                        0.7416487904590888,
                        0.7416487904590888,
                        0.7416740045630911,
                        0.7467352721935584,
                        0.7552073737042055,
                        0.7552326284306445,
                        0.7577410378866258,
                        0.7577344723873682,
                        0.7573195427154136,
                        0.7479494214236384,
                        0.7479573856140954,
                        0.7479746499879586,
                        0.7479849815340289,
                        0.7561184249609694,
                        0.7624018948643082,
                        0.7664678165610375,
                        0.7664751521777626,
                        0.7602935249243234,
                        0.7600467216514943,
                        0.7436193156606876,
                        0.7416487904590888
                      ]
                    }
                  }
                }
              },
              "AIA_CZ2": {
                "residential": {
                  "winter": {
                    "months": [
                      1,
                      2,
                      12
                    ],
                    "annual_days": 90.25,
                    "rates": {
                      "weekday": [
                        0.7316915700768777,
                        0.7316915700768777,
                        0.7316915700768777,
                        0.7316915700768777,
                        0.7317033321035448,
                        0.7552900300918178,
                        0.8226544622776824,
                        0.9142687771174831,
                        0.9814930775863582,
                        1.0941773089233215,
                        1.1241661637494853,
                        1.074363692826858,
                        1.0809367319784724,
                        1.0605096167219756,
                        1.01922290180229,
                        1.0409148720513626,
                        1.1016900648582957,
                        1.3289191700466993,
                        1.3775524377575605,
                        1.315400343229818,
                        1.0669000433260145,
                        0.8719960078696121,
                        0.7921397366659657,
                        0.7500601852594996
                      ],
                      "weekend": [
                        0.736735889566547,
                        0.736735889566547,
                        0.736735889566547,
                        0.736735889566547,
                        0.736735889566547,
                        0.7556686447763918,
                        0.7608448042659574,
                        0.7836885461000579,
                        0.7895174392127189,
                        0.7881823961211574,
                        0.7914929816126687,
                        0.7923744083418933,
                        0.7820493019495912,
                        0.7630498791669946,
                        0.7824001722895619,
                        0.7843539880600577,
                        0.7886557756808379,
                        0.8215662381729987,
                        0.8221785414753836,
                        0.8246083246223305,
                        0.8021083104675605,
                        0.7901060924580815,
                        0.7690513257992789,
                        0.7478062026728524
                      ]
                    }
                  },
                  "summer": {
                    "months": [
                      5,
                      6,
                      7,
                      8,
                      9
                    ],
                    "annual_days": 153,
                    "rates": {
                      "weekday": [
                        0.7495809207750027,
                        0.7495809207750027,
                        0.7495809207750027,
                        0.7495809207750027,
                        0.7495809207750027,
                        0.7701088403081495,
                        0.7806797725722616,
                        0.8301777081608774,
                        0.8917226599786222,
                        0.9742296364313614,
                        1.089548412424175,
                        1.1544829173735325,
                        1.2603907056637045,
                        1.3308406888455804,
                        1.4145525381994923,
                        1.441126760789947,
                        1.5681838098052348,
                        1.6474108034992343,
                        1.5699271469049405,
                        1.3368917746211497,
                        0.9677042303951087,
                        0.8835845958175031,
                        0.7908433426928246,
                        0.7691810327982223
                      ],
                      "weekend": [
                        0.7528922978925378,
                        0.7528922978925378,
                        0.7528922978925378,
                        0.7528922978925378,
                        0.7528922978925378,
                        0.7714634479748301,
                        0.7759037884307903,
                        0.7882915296894144,
                        0.7975629053927803,
                        0.7965490779661469,
                        0.805591873222608,
                        0.8067656546809132,
                        0.8015095289042871,
                        0.7844497412741083,
                        0.8032083366451127,
                        0.805718897437873,
                        0.8100221458492244,
                        0.8395995605437871,
                        0.8398195794078622,
                        0.8359281181795717,
                        0.8132372556286078,
                        0.8076054187720259,
                        0.7825917829699133,
                        0.7639774572644759
                      ]
                    }
                  },
                  "intermediate": {
                    "months": [
                      10,
                      11,
                      3,
                      4
                    ],
                    "annual_days": 122,
                    "rates": {
                      "weekday": [
                        0.7319509654359847,
                        0.7319509654359847,
                        0.7319509654359847,
                        0.7319509654359847,
                        0.731952213469939,
                        0.7555141644645146,
                        0.8021532696997766,
                        0.8857141994766777,
                        0.9512848637324858,
                        1.0721074323084783,
                        1.1321012137563657,
                        1.0824587232062468,
                        1.089252569161349,
                        1.069647268295233,
                        1.028289784228049,
                        1.053236743620014,
                        1.1342596596822652,
                        1.340907914653053,
                        1.33170667913807,
                        1.2076728986790333,
                        1.0437703009592394,
                        0.8704707399447128,
                        0.791669260291943,
                        0.7503172636287222
                      ],
                      "weekend": [
                        0.736731430869897,
                        0.736731430869897,
                        0.736731430869897,
                        0.736731430869897,
                        0.736731430869897,
                        0.7556543547835727,
                        0.7606268276779431,
                        0.7653773920828586,
                        0.7773178387288284,
                        0.7759572190534243,
                        0.7841418608058195,
                        0.7850774789998485,
                        0.7820553236796779,
                        0.7631893126810845,
                        0.7829557537431892,
                        0.7846673103962851,
                        0.7889832582334468,
                        0.8215721731612435,
                        0.8215982921648831,
                        0.824030467376909,
                        0.8006996675592478,
                        0.7900837412439528,
                        0.7685614079236551,
                        0.74779566555065
                      ]
                    }
                  }
                },
                "commercial": {
                  "winter": {
                    "months": [
                      1,
                      2,
                      12
                    ],
                    "annual_days": 90.25,
                    "rates": {
                      "weekday": [
                        0.7489003805767075,
                        0.7489003805767075,
                        0.7489028501583815,
                        0.748908802955999,
                        0.7489316005122001,
                        0.7491560471027127,
                        0.8386612785345405,
                        0.9709525424394335,
                        1.0435128459658074,
                        1.172892178518513,
                        1.096230743720652,
                        1.0772113337597469,
                        0.9819845805007349,
                        0.9819074875426435,
                        0.9924856024110523,
                        0.9944809952866005,
                        1.0516121867438153,
                        1.2161107357049625,
                        1.3097832128437588,
                        1.30447848135753,
                        1.0886052587360664,
                        0.9146114458170342,
                        0.80814737726382,
                        0.7489003805767075
                      ],
                      "weekend": [
                        0.7666624354825922,
                        0.7666624354825922,
                        0.7666624354825922,
                        0.7666624354825922,
                        0.7666624354825922,
                        0.7667893680287652,
                        0.8087306096287916,
                        0.8139432391419437,
                        0.813912277620187,
                        0.8170998152480557,
                        0.8171154156666702,
                        0.8149084815605357,
                        0.7799785065474677,
                        0.7799793543143111,
                        0.7892742010449716,
                        0.7892979200868718,
                        0.7923123521839034,
                        0.835069517357263,
                        0.8655071042675646,
                        0.8655115273989213,
                        0.8289467702084574,
                        0.8267284085685997,
                        0.8140540510890655,
                        0.7666624354825922
                      ]
                    }
                  },
                  "summer": {
                    "months": [
                      5,
                      6,
                      7,
                      8,
                      9
                    ],
                    "annual_days": 153,
                    "rates": {
                      "weekday": [
                        0.7888287270138659,
                        0.7888287270138659,
                        0.7888287270138659,
                        0.7888287270138659,
                        0.7888287270138659,
                        0.7889488774252921,
                        0.8117322469185145,
                        0.8725727207461356,
                        0.9472194328517902,
                        1.0640937974006555,
                        1.1122814787292419,
                        1.1079980011786625,
                        1.2022337775355092,
                        1.374862076069252,
                        1.4116271571507053,
                        1.42169878705685,
                        1.538086506912954,
                        1.5638640297026465,
                        1.370689511585874,
                        1.3310685701071516,
                        1.0471975593592247,
                        0.9300086923379542,
                        0.8056656688356038,
                        0.7888287270138659
                      ],
                      "weekend": [
                        0.8041639782853334,
                        0.8041639782853334,
                        0.8041639782853334,
                        0.8041639782853334,
                        0.8041639782853334,
                        0.8042833546487722,
                        0.8059045114211196,
                        0.8087565423738539,
                        0.8193822228963382,
                        0.8201909295254707,
                        0.8227407497202675,
                        0.8211909636372704,
                        0.8319146255259092,
                        0.8397309932132342,
                        0.8509498374669687,
                        0.8510386280261835,
                        0.8535573691890912,
                        0.8568336459738631,
                        0.8494188553460068,
                        0.8682695618121168,
                        0.8296745210574148,
                        0.8252382083020103,
                        0.8101263601214234,
                        0.8041639782853334
                      ]
                    }
                  },
                  "intermediate": {
                    "months": [
                      10,
                      11,
                      3,
                      4
                    ],
                    "annual_days": 122,
                    "rates": {
                      "weekday": [
                        0.756489537642857,
                        0.756489537642857,
                        0.7564914312959691,
                        0.7564939193073573,
                        0.7565038575306243,
                        0.7567005299352499,
                        0.8318943261200098,
                        0.9320658008883707,
                        1.0075917440268958,
                        1.1265718415744808,
                        1.0963488725983204,
                        1.0774369018947785,
                        0.9926434035932892,
                        0.9925749361706508,
                        1.0032681737491391,
                        1.005487618240672,
                        1.074814886471723,
                        1.2200417150237457,
                        1.2378229178933422,
                        1.23217934789683,
                        1.0478403122225513,
                        0.9122333991280481,
                        0.8052972648207765,
                        0.756489537642857
                      ],
                      "weekend": [
                        0.7742342455804521,
                        0.7742342455804521,
                        0.7742342455804521,
                        0.7742342455804521,
                        0.7742342455804521,
                        0.7743566628466987,
                        0.8061573106164389,
                        0.8103010485753738,
                        0.8114269022464343,
                        0.814487086689793,
                        0.8144998761998503,
                        0.8122826564703403,
                        0.7875530074265378,
                        0.7875585363407336,
                        0.7982479346248332,
                        0.7982551070087738,
                        0.8012709873668807,
                        0.8470173419649478,
                        0.8643022337672288,
                        0.8643073263118718,
                        0.8264878614846082,
                        0.8242472972598779,
                        0.8112265316252133,
                        0.7742342455804521
                      ]
                    }
                  }
                }
              }
            },
            "emissions": {
              "AIA_CZ1": {
                "winter": {
                  "months": [
                    1,
                    2,
                    12
                  ],
                  "annual_days": 90.25,
                  "factors": [
                    1.0808327943771008,
                    1.0947294879594474,
                    1.0909604832627986,
                    0.997259933763779,
                    1.0157987104859902,
                    1.0160614041206557,
                    1.0477835926945642,
                    1.000430414155741,
                    1.023557292451596,
                    0.960032661017396,
                    0.917036500578013,
                    0.9705004448862705,
                    0.9907681555516679,
                    1.0253381814057205,
                    0.9844841561876502,
                    0.9042117573723634,
                    1.0284123659853506,
                    1.0036148259369406,
                    0.9833833200372775,
                    0.952786486602425,
                    0.9137505041285251,
                    0.9183607987573171,
                    1.0297440696206162,
                    1.0501616586607956
                  ]
                },
                "summer": {
                  "months": [
                    5,
                    6,
                    7,
                    8
                  ],
                  "annual_days": 123,
                  "factors": [
                    1.1435710315058578,
                    1.1855937369569567,
                    1.1841115412910492,
                    1.1711267994327952,
                    1.138416978159702,
                    1.0879526698838258,
                    1.047850567207246,
                    0.9915300582880294,
                    0.9257377330283679,
                    0.9323171624462354,
                    0.9230809453005281,
                    0.9171957664527647,
                    0.9220163795107141,
                    0.9322139542622108,
                    0.9698324615055369,
                    0.9801952991546521,
                    0.9454291136003109,
                    0.9252177083898578,
                    0.9350063389981491,
                    0.941638621913107,
                    0.8621879023886238,
                    0.8691889278276335,
                    0.9908346745164235,
                    1.077753627979422
                  ]
                },
                "intermediate": {
                  "months": [
                    9,
                    10,
                    11,
                    3,
                    4
                  ],
                  "annual_days": 152,
                  "factors": [
                    1.0658956503894756,
                    1.0727670538462724,
                    1.0631207028580707,
                    1.046332293005439,
                    1.015708019925993,
                    1.026753672777928,
                    1.021262021827931,
                    0.9949980406706456,
                    0.9757903062587946,
                    0.9396316891528453,
                    0.9466447200833301,
                    0.9476982359938386,
                    0.9727191746106075,
                    0.9655198479731756,
                    0.9631011731360967,
                    0.9523456404643373,
                    1.008536357395883,
                    1.0106262570856785,
                    1.020217337466093,
                    0.995225325404544,
                    0.9852466168013723,
                    0.9828527161667133,
                    0.9910882940666929,
                    1.035918852638241
                  ]
                }
              },
              "AIA_CZ2": {
                "winter": {
                  "months": [
                    1,
                    2,
                    12
                  ],
                  "annual_days": 90.25,
                  "factors": [
                    1.0535658672762813,
                    1.096526332978691,
                    1.0771622576644349,
                    0.9861997106791047,
                    0.9811011622781287,
                    0.9790545864565884,
                    1.0263760698119722,
                    0.9956915484970449,
                    1.0078219995749305,
                    0.9716016307332266,
                    0.9493542036289454,
                    0.9813922518937052,
                    0.9776775198440708,
                    1.0141604106509272,
                    0.9850587993552904,
                    0.9316484224260333,
                    0.9949688278695517,
                    1.01055961509294,
                    1.017103893763983,
                    0.9590350781891323,
                    0.9704093503233061,
                    0.9672264348385085,
                    1.0146181260811424,
                    1.0516859000920609
                  ]
                },
                "summer": {
                  "months": [
                    5,
                    6,
                    7,
                    8
                  ],
                  "annual_days": 123,
                  "factors": [
                    1.0872807529906836,
                    1.156405393861518,
                    1.1726965583124587,
                    1.1707509351020557,
                    1.1360032758413263,
                    1.0739651110736461,
                    1.0479111560933447,
                    1.005681341580094,
                    0.9408650160642685,
                    0.9353227765467297,
                    0.9366381324121216,
                    0.9278327467710181,
                    0.9416270357604664,
                    0.9513652843599338,
                    0.9772729438597565,
                    0.9942083133989313,
                    0.9640059582039975,
                    0.9578643188353364,
                    0.958175448972868,
                    0.9836535108930796,
                    0.9166676067058098,
                    0.860476258184747,
                    0.9084788781257114,
                    0.9948512460500967
                  ]
                },
                "intermediate": {
                  "months": [
                    9,
                    10,
                    11,
                    3,
                    4
                  ],
                  "annual_days": 152,
                  "factors": [
                    1.077260761114282,
                    1.091509595687165,
                    1.0822368284391288,
                    1.0565532492467509,
                    1.0136147466311083,
                    1.0078873939572586,
                    1.016867635285059,
                    0.993705048362059,
                    0.9600070040455235,
                    0.9425520430464386,
                    0.9424622396992823,
                    0.9527367144684524,
                    0.9831562117694889,
                    0.9724453429835529,
                    0.9870323960038236,
                    0.9829837910623043,
                    1.0028892034459056,
                    1.0037169087173556,
                    1.0251019365755865,
                    0.9931279014580454,
                    0.974609000569764,
                    0.943542113476512,
                    0.9581810311526768,
                    1.035820902802477
                  ]
                }
              }
            }
          }
        cls.sample_mseg_in = {
            "AIA_CZ1": {
                "single family home": {
                    "total square footage": {"2009": 100, "2010": 200},
                    "total homes": {"2009": 1000, "2010": 1000},
                    "new homes": {"2009": 100, "2010": 50},
                    "electricity": {
                      "heating": {
                            "demand": {
                                "windows conduction": {
                                    "stock": "NA",
                                    "energy": {"2009": 0, "2010": 0}},
                                "windows solar": {
                                    "stock": "NA",
                                    "energy": {"2009": 1, "2010": 1}},
                                "infiltration": {
                                    "stock": "NA",
                                    "energy": {"2009": 10, "2010": 10}}},
                            "supply": {
                                "resistance heat": {
                                    "stock": {"2009": 2, "2010": 2},
                                    "energy": {"2009": 2, "2010": 2}},
                                "ASHP": {
                                    "stock": {"2009": 3, "2010": 3},
                                    "energy": {"2009": 3, "2010": 3}},
                                "GSHP": {
                                    "stock": {"2009": 4, "2010": 4},
                                    "energy": {"2009": 4, "2010": 4}}}},
                      "cooling": {
                            "demand": {
                                "windows conduction": {
                                    "stock": "NA",
                                    "energy": {"2009": 5, "2010": 5}},
                                "windows solar": {
                                    "stock": "NA",
                                    "energy": {"2009": 6, "2010": 6}},
                                "infiltration": {
                                    "stock": "NA",
                                    "energy": {"2009": 10, "2010": 10}}},
                            "supply": {
                                "central AC": {
                                    "stock": {"2009": 7, "2010": 7},
                                    "energy": {"2009": 7, "2010": 7}},
                                "room AC": {
                                    "stock": {"2009": 8, "2010": 8},
                                    "energy": {"2009": 8, "2010": 8}},
                                "ASHP": {
                                    "stock": {"2009": 9, "2010": 9},
                                    "energy": {"2009": 9, "2010": 9}},
                                "GSHP": {
                                    "stock": {"2009": 10, "2010": 10},
                                    "energy": {"2009": 10, "2010": 10}}}}
                    },
                    "natural gas": {
                        "water heating": {
                            "stock": {"2009": 15, "2010": 15},
                            "energy": {"2009": 15, "2010": 15}}}}},
            "AIA_CZ2": {
                "single family home": {
                    "total square footage": {"2009": 500, "2010": 600},
                    "total homes": {"2009": 1000, "2010": 1000},
                    "new homes": {"2009": 100, "2010": 50},
                    "electricity": {
                        "heating": {
                            "demand": {
                                "windows conduction": {
                                    "stock": "NA",
                                    "energy": {"2009": 0, "2010": 0}},
                                "windows solar": {
                                    "stock": "NA",
                                    "energy": {"2009": 1, "2010": 1}},
                                "infiltration": {
                                    "stock": "NA",
                                    "energy": {"2009": 10, "2010": 10}}},
                            "supply": {
                                "resistance heat": {
                                    "stock": {"2009": 2, "2010": 2},
                                    "energy": {"2009": 2, "2010": 2}},
                                "ASHP": {
                                    "stock": {"2009": 3, "2010": 3},
                                    "energy": {"2009": 3, "2010": 3}},
                                "GSHP": {
                                    "stock": {"2009": 4, "2010": 4},
                                    "energy": {"2009": 4, "2010": 4}}}},
                        "cooling": {
                            "demand": {
                                "windows conduction": {
                                    "stock": "NA",
                                    "energy": {"2009": 5, "2010": 5}},
                                "windows solar": {
                                    "stock": "NA",
                                    "energy": {"2009": 6, "2010": 6}},
                                "infiltration": {
                                    "stock": "NA",
                                    "energy": {"2009": 10, "2010": 10}}},
                            "supply": {
                                "central AC": {
                                    "stock": {"2009": 7, "2010": 7},
                                    "energy": {"2009": 7, "2010": 7}},
                                "room AC": {
                                    "stock": {"2009": 8, "2010": 8},
                                    "energy": {"2009": 8, "2010": 8}},
                                "ASHP": {
                                    "stock": {"2009": 9, "2010": 9},
                                    "energy": {"2009": 9, "2010": 9}},
                                "GSHP": {
                                    "stock": {"2009": 10, "2010": 10},
                                    "energy": {"2009": 10, "2010": 10}}}}}}}}
        cls.sample_cpl_in = {
            "AIA_CZ1": {
                "single family home": {
                    "electricity": {
                        "heating": {
                            "demand": {
                                "windows conduction": {
                                    "performance": {
                                        "typical": {"2009": 1, "2010": 1},
                                        "best": {"2009": 1, "2010": 1},
                                        "units": "R Value",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 1, "2010": 1},
                                        "best": {"2009": 1, "2010": 1},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 10, "2010": 10},
                                        "range": {"2009": 1, "2010": 1},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "windows solar": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "SHGC",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "infiltration": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 3},
                                        "best": {"2009": 2, "2010": 3},
                                        "units": "ACH50",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}},
                            "supply": {
                                "resistance heat": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "ASHP": {
                                    "performance": {
                                        "typical": {"2009": 3, "2010": 3},
                                        "best": {"2009": 3, "2010": 3},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 3, "2010": 3},
                                        "best": {"2009": 3, "2010": 3},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 30, "2010": 30},
                                        "range": {"2009": 3, "2010": 3},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "GSHP": {
                                    "performance": {
                                        "typical": {"2009": 4, "2010": 4},
                                        "best": {"2009": 4, "2010": 4},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 4, "2010": 4},
                                        "best": {"2009": 4, "2010": 4},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 40, "2010": 40},
                                        "range": {"2009": 4, "2010": 4},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}}},
                        "cooling": {
                            "demand": {
                                "windows conduction": {
                                    "performance": {
                                        "typical": {
                                            "new": {"2009": 8, "2010": 8},
                                            "existing": {
                                                "2009": 8, "2010": 8}
                                            },
                                        "best": {"2009": 8, "2010": 8},
                                        "units": "R Value",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 8, "2010": 8},
                                        "best": {"2009": 8, "2010": 8},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 80, "2010": 80},
                                        "range": {"2009": 8, "2010": 8},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "windows solar": {
                                    "performance": {
                                        "typical": {"2009": 9, "2010": 9},
                                        "best": {"2009": 9, "2010": 9},
                                        "units": "SHGC",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 9, "2010": 9},
                                        "best": {"2009": 9, "2010": 9},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 90, "2010": 90},
                                        "range": {"2009": 9, "2010": 9},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "infiltration": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 3},
                                        "best": {"2009": 2, "2010": 3},
                                        "units": "ACH50",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}},
                            "supply": {
                                "central AC": {
                                    "performance": {
                                        "typical": {"2009": 10, "2010": 10},
                                        "best": {"2009": 10, "2010": 10},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 10, "2010": 10},
                                        "best": {"2009": 10, "2010": 10},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 100, "2010": 100},
                                        "range": {"2009": 10, "2010": 10},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "room AC": {
                                    "performance": {
                                        "typical": {"2009": 11, "2010": 11},
                                        "best": {"2009": 11, "2010": 11},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 11, "2010": 11},
                                        "best": {"2009": 11, "2010": 11},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 110, "2010": 110},
                                        "range": {"2009": 11, "2010": 11},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "ASHP": {
                                    "performance": {
                                        "typical": {"2009": 12, "2010": 12},
                                        "best": {"2009": 12, "2010": 12},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 12, "2010": 12},
                                        "best": {"2009": 12, "2010": 12},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 120, "2010": 120},
                                        "range": {"2009": 12, "2010": 12},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "GSHP": {
                                    "performance": {
                                        "typical": {"2009": 13, "2010": 13},
                                        "best": {"2009": 13, "2010": 13},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 13, "2010": 13},
                                        "best": {"2009": 13, "2010": 13},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 130, "2010": 130},
                                        "range": {"2009": 13, "2010": 13},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}}}},
                    "natural gas": {
                        "water heating": {
                            "performance": {
                                "typical": {"2009": 18, "2010": 18},
                                "best": {"2009": 18, "2010": 18},
                                "units": "EF",
                                "source":
                                "EIA AEO"},
                            "installed cost": {
                                "typical": {"2009": 18, "2010": 18},
                                "best": {"2009": 18, "2010": 18},
                                "units": "2014$/unit",
                                "source": "EIA AEO"},
                            "lifetime": {
                                "average": {"2009": 180, "2010": 180},
                                "range": {"2009": 18, "2010": 18},
                                "units": "years",
                                "source": "EIA AEO"},
                            "consumer choice": {
                                "competed market share": {
                                    "source": "EIA AEO",
                                    "model type": "logistic regression",
                                    "parameters": {
                                        "b1": {"2009": "NA", "2010": "NA"},
                                        "b2": {"2009": "NA",
                                               "2010": "NA"}}},
                                "competed market": {
                                    "source": "COBAM",
                                    "model type": "bass diffusion",
                                    "parameters": {
                                        "p": "NA",
                                        "q": "NA"}}}}}}},
            "AIA_CZ2": {
                "single family home": {
                    "electricity": {
                        "heating": {
                            "demand": {
                                "windows conduction": {
                                    "performance": {
                                        "typical": {"2009": 1, "2010": 1},
                                        "best": {"2009": 1, "2010": 1},
                                        "units": "R Value",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 1, "2010": 1},
                                        "best": {"2009": 1, "2010": 1},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 10, "2010": 10},
                                        "range": {"2009": 1, "2010": 1},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "windows solar": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "SHGC",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "infiltration": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 3},
                                        "best": {"2009": 2, "2010": 3},
                                        "units": "ACH50",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}},
                            "supply": {
                                "resistance heat": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "ASHP": {
                                    "performance": {
                                        "typical": {"2009": 3, "2010": 3},
                                        "best": {"2009": 3, "2010": 3},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 3, "2010": 3},
                                        "best": {"2009": 3, "2010": 3},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 30, "2010": 30},
                                        "range": {"2009": 3, "2010": 3},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "GSHP": {
                                    "performance": {
                                        "typical": {"2009": 4, "2010": 4},
                                        "best": {"2009": 4, "2010": 4},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 4, "2010": 4},
                                        "best": {"2009": 4, "2010": 4},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 40, "2010": 40},
                                        "range": {"2009": 4, "2010": 4},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}}},
                        "cooling": {
                            "demand": {
                                "windows conduction": {
                                    "performance": {
                                        "typical": {"2009": 8, "2010": 8},
                                        "best": {"2009": 8, "2010": 8},
                                        "units": "R Value",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 8, "2010": 8},
                                        "best": {"2009": 8, "2010": 8},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 80, "2010": 80},
                                        "range": {"2009": 8, "2010": 8},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "windows solar": {
                                    "performance": {
                                        "typical": {"2009": 9, "2010": 9},
                                        "best": {"2009": 9, "2010": 9},
                                        "units": "SHGC",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 9, "2010": 9},
                                        "best": {"2009": 9, "2010": 9},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 90, "2010": 90},
                                        "range": {"2009": 9, "2010": 9},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "infiltration": {
                                    "performance": {
                                        "typical": {"2009": 2, "2010": 3},
                                        "best": {"2009": 2, "2010": 3},
                                        "units": "ACH50",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 2, "2010": 2},
                                        "best": {"2009": 2, "2010": 2},
                                        "units": "2014$/ft^2 floor",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 20, "2010": 20},
                                        "range": {"2009": 2, "2010": 2},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}},
                            "supply": {
                                "central AC": {
                                    "performance": {
                                        "typical": {"2009": 10, "2010": 10},
                                        "best": {"2009": 10, "2010": 10},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 10, "2010": 10},
                                        "best": {"2009": 10, "2010": 10},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 100, "2010": 100},
                                        "range": {"2009": 10, "2010": 10},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "room AC": {
                                    "performance": {
                                        "typical": {"2009": 11, "2010": 11},
                                        "best": {"2009": 11, "2010": 11},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 11, "2010": 11},
                                        "best": {"2009": 11, "2010": 11},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 110, "2010": 110},
                                        "range": {"2009": 11, "2010": 11},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "ASHP": {
                                    "performance": {
                                        "typical": {"2009": 12, "2010": 12},
                                        "best": {"2009": 12, "2010": 12},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 12, "2010": 12},
                                        "best": {"2009": 12, "2010": 12},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 120, "2010": 120},
                                        "range": {"2009": 12, "2010": 12},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}},
                                "GSHP": {
                                    "performance": {
                                        "typical": {"2009": 13, "2010": 13},
                                        "best": {"2009": 13, "2010": 13},
                                        "units": "COP",
                                        "source":
                                        "EIA AEO"},
                                    "installed cost": {
                                        "typical": {"2009": 13, "2010": 13},
                                        "best": {"2009": 13, "2010": 13},
                                        "units": "2014$/unit",
                                        "source": "EIA AEO"},
                                    "lifetime": {
                                        "average": {"2009": 130, "2010": 130},
                                        "range": {"2009": 13, "2010": 13},
                                        "units": "years",
                                        "source": "EIA AEO"},
                                    "consumer choice": {
                                        "competed market share": {
                                            "source": "EIA AEO",
                                            "model type":
                                                "logistic regression",
                                            "parameters": {
                                                "b1": {"2009": "NA",
                                                       "2010": "NA"},
                                                "b2": {"2009": "NA",
                                                       "2010": "NA"}}},
                                        "competed market": {
                                            "source": "COBAM",
                                            "model type": "bass diffusion",
                                            "parameters": {
                                                "p": "NA",
                                                "q": "NA"}}}}}}}}}}
        cls.convert_data = {}  # Blank for now
        cls.measures_ok_in = [{
            "name": "sample measure to prepare",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": {
                "new": 25, "existing": 25},
            "energy_efficiency_units": "EF",
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": "single family home",
            "climate_zone": "AIA_CZ1",
            "fuel_type": "natural gas",
            "fuel_switch_to": None,
            "end_use": "water heating",
            "technology": None,
            "time_sensitive_valuation": None},
            {
            "name": "sample time sensitive measure to prepare",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": 0.2,
            "energy_efficiency_units": "relative savings (constant)",
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": "single family home",
            "climate_zone": "AIA_CZ1",
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": "heating",
            "technology": "ASHP",
            "time_sensitive_valuation": {
              "conventional": {
                "start": 6, "stop": 10}}},
            {
            "name": "sample time sens. measure 2 to prepare",
            "markets": None,
            "installed_cost": 25,
            "cost_units": "2014$/unit",
            "energy_efficiency": 1,
            "energy_efficiency_units": "relative savings (constant)",
            "market_entry_year": None,
            "market_exit_year": None,
            "product_lifetime": 1,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "bldg_type": "single family home",
            "climate_zone": "AIA_CZ1",
            "fuel_type": "electricity",
            "fuel_switch_to": None,
            "end_use": "heating",
            "technology": "ASHP",
            "time_sensitive_valuation": {
              "conventional": {
                "start": 6, "stop": 10}}}]
        cls.ok_out = [{
            "stock": {
                "total": {
                    "all": {"2009": 15, "2010": 15},
                    "measure": {"2009": 15, "2010": 15}},
                "competed": {
                    "all": {"2009": 15, "2010": 15},
                    "measure": {"2009": 15, "2010": 15}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 15.15, "2010": 15.15},
                    "efficient": {"2009": 10.908, "2010": 10.908}},
                "competed": {
                    "baseline": {"2009": 15.15, "2010": 15.15},
                    "efficient": {"2009": 10.908, "2010": 10.908}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 856.2139, "2010": 832.0021},
                    "efficient": {"2009": 616.474, "2010": 599.0415}},
                "competed": {
                    "baseline": {"2009": 856.2139, "2010": 832.0021},
                    "efficient": {"2009": 616.474, "2010": 599.0415}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 270, "2010": 270},
                        "efficient": {"2009": 375, "2010": 375}},
                    "competed": {
                        "baseline": {"2009": 270, "2010": 270},
                        "efficient": {"2009": 375, "2010": 375}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 170.892, "2010": 163.317},
                        "efficient": {"2009": 123.0422, "2010": 117.5882}},
                    "competed": {
                        "baseline": {"2009": 170.892, "2010": 163.317},
                        "efficient": {"2009": 123.0422, "2010": 117.5882}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 28255.06, "2010": 27456.07},
                        "efficient": {"2009": 20343.64, "2010": 19768.37}},
                    "competed": {
                        "baseline": {"2009": 28255.06, "2010": 27456.07},
                        "efficient": {"2009": 20343.64, "2010": 19768.37}}}},
            "lifetime": {"baseline": {"2009": 180, "2010": 180},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 3, "2010": 3},
                    "measure": {"2009": 3, "2010": 3}},
                "competed": {
                    "all": {"2009": 3, "2010": 3},
                    "measure": {"2009": 3, "2010": 3}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 9.57, "2010": 9.6},
                    "efficient": {"2009": 9.053148, "2010": 9.081528}},
                "competed": {
                    "baseline": {"2009": 9.57, "2010": 9.6},
                    "efficient": {"2009": 9.053148, "2010": 9.081528}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 545.2854, "2010": 540.4633},
                    "efficient": {"2009": 517.0981, "2010": 512.5253}},
                "competed": {
                    "baseline": {"2009": 545.2854, "2010": 540.4633},
                    "efficient": {"2009": 517.0981, "2010": 512.5253}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 9, "2010": 9},
                        "efficient": {"2009": 75, "2010": 75}},
                    "competed": {
                        "baseline": {"2009": 9, "2010": 9},
                        "efficient": {"2009": 75, "2010": 75}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 83.16846, "2010": 79.56214},
                        "efficient": {"2009": 78.88245, "2010": 75.46198}},
                    "competed": {
                        "baseline": {"2009": 83.16846, "2010": 79.56214},
                        "efficient": {"2009": 78.88245, "2010": 75.46198}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 17994.42, "2010": 17835.29},
                        "efficient": {"2009": 17064.24, "2010": 16913.33}},
                    "competed": {
                        "baseline": {"2009": 17994.42, "2010": 17835.29},
                        "efficient": {"2009": 17064.24, "2010": 16913.33}}}},
            "lifetime": {"baseline": {"2009": 30, "2010": 30},
                         "measure": 1}},
            {
            "stock": {
                "total": {
                    "all": {"2009": 3, "2010": 3},
                    "measure": {"2009": 3, "2010": 3}},
                "competed": {
                    "all": {"2009": 3, "2010": 3},
                    "measure": {"2009": 3, "2010": 3}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 9.57, "2010": 9.6},
                    "efficient": {"2009": 6.986, "2010": 7.0079}},
                "competed": {
                    "baseline": {"2009": 9.57, "2010": 9.6},
                    "efficient": {"2009": 6.986, "2010": 7.0079}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 545.2854, "2010": 540.4633},
                    "efficient": {"2009": 399.3145, "2010": 395.7832}},
                "competed": {
                    "baseline": {"2009": 545.2854, "2010": 540.4633},
                    "efficient": {"2009": 399.3145, "2010": 395.7832}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 9, "2010": 9},
                        "efficient": {"2009": 75, "2010": 75}},
                    "competed": {
                        "baseline": {"2009": 9, "2010": 9},
                        "efficient": {"2009": 75, "2010": 75}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 83.16846, "2010": 79.56214},
                        "efficient": {"2009": 61.74057, "2010": 59.0634}},
                    "competed": {
                        "baseline": {"2009": 83.16846, "2010": 79.56214},
                        "efficient": {"2009": 61.74057, "2010": 59.0634}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 17994.42, "2010": 17835.29},
                        "efficient": {"2009": 13177.38, "2010": 13060.85}},
                    "competed": {
                        "baseline": {"2009": 17994.42, "2010": 17835.29},
                        "efficient": {"2009": 13177.38, "2010": 13060.85}}}},
            "lifetime": {"baseline": {"2009": 30, "2010": 30},
                         "measure": 1}}]

    def test_fillmeas_ok(self):
        """Test 'prepare_measures' function given valid measure inputs.

        Note:
            Ensure that function properly identifies which input measures
            require updating and that the updates are performed correctly.
        """
        measures_out = ecm_prep.prepare_measures(
            self.measures_ok_in, self.convert_data, self.sample_mseg_in,
            self.sample_cpl_in, self.handyvars, self.cbecs_sf_byvint,
            self.tsv_data, self.base_dir, self.verbose)
        for oc in range(0, len(self.ok_out)):
            self.dict_check(
                measures_out[oc].markets[
                    "Technical potential"]["master_mseg"], self.ok_out[oc])


class MergeMeasuresandApplyBenefitsTest(unittest.TestCase, CommonMethods):
    """Test 'merge_measures' and 'apply_pkg_benefits' functions.

    Ensure that the 'merge_measures' function correctly assembles a series of
    attributes for individual measures into attributes for a packaged measure,
    and that the 'apply_pkg_benefits' function correctly applies additional
    energy savings and installed cost benefits for a package measure.

    Attributes:
        sample_measures_in (list): List of valid sample measure attributes
            to package.
        sample_package_name (string): Sample packaged measure name.
        sample_package_in_test1 (object): Sample packaged measure object to
            update in the test of the 'merge_measures' function.
        sample_package_in_test2 (object): Sample packaged measure object to
            initialize for the test of the 'apply_pkg_benefits' function.
        genattr_ok_out_test1 (list): General attributes that should be yielded
            for the packaged measure in the 'merge_measures' test, given valid
            sample measures to merge.
        markets_ok_out_test1 (dict): Packaged measure stock, energy, carbon,
            and cost data that should be yielded in the 'merge_measures' test,
            given valid sample measures to merge.
        mseg_ok_in_test2 (dict): Energy, carbon, and cost data to apply
            additional energy savings and cost reduction benefits to in the
            'apply_pkg_benefits' test.
        mseg_ok_out_test2 (dict): Updated energy, carbon, and cost data
            that should be yielded in 'apply_pkg_benefits' test, given valid
            input data to apply packaging benefits to.
    """

    @classmethod
    def setUpClass(cls):
        """Define variables and objects for use across all class functions."""
        # Base directory
        base_dir = os.getcwd()
        # Define additional energy savings and cost reduction benefits to
        # apply to the energy, carbon, and cost data for a package in the
        # 'merge_measures' test
        benefits_test1 = {
            "energy savings increase": 0,
            "cost reduction": 0}
        # Define additional energy savings and cost reduction benefits to
        # apply to the energy, carbon, and cost data for a package in the
        # 'apply_pkg_benefits' test
        benefits_test2 = {
            "energy savings increase": 0.3,
            "cost reduction": 0.2}
        # Useful global variables for the sample package measure objects
        handyvars = ecm_prep.UsefulVars(base_dir,
                                        ecm_prep.UsefulInputFiles())
        # Hard code aeo_years to fit test years
        handyvars.aeo_years = ["2009", "2010"]
        # Define a series of sample measures to package
        sample_measures_in = [{
            "name": "sample measure pkg 1",
            "market_entry_year": None,
            "market_exit_year": None,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ2"],
            "bldg_type": ["single family home"],
            "fuel_type": ["natural gas"],
            "fuel_switch_to": None,
            "end_use": {"primary": ["water heating"],
                        "secondary": None},
            "technology": [None],
            "technology_type": {
                "primary": "supply", "secondary": None},
            "markets": {
                "Technical potential": {
                    "master_mseg": {
                        "stock": {
                            "total": {
                                "all": {"2009": 40, "2010": 40},
                                "measure": {"2009": 24, "2010": 24}},
                            "competed": {
                                "all": {"2009": 20, "2010": 20},
                                "measure": {"2009": 4, "2010": 4}}},
                        "energy": {
                            "total": {
                                "baseline": {"2009": 80, "2010": 80},
                                "efficient": {"2009": 48, "2010": 48}},
                            "competed": {
                                "baseline": {"2009": 40, "2010": 40},
                                "efficient": {"2009": 8, "2010": 8}}},
                        "carbon": {
                            "total": {
                                "baseline": {"2009": 120, "2010": 120},
                                "efficient": {"2009": 72, "2010": 72}},
                            "competed": {
                                "baseline": {"2009": 60, "2010": 60},
                                "efficient": {"2009": 12, "2010": 12}}},
                        "cost": {
                            "stock": {
                                "total": {
                                    "baseline": {"2009": 40, "2010": 40},
                                    "efficient": {"2009": 72, "2010": 72}},
                                "competed": {
                                    "baseline": {"2009": 40, "2010": 40},
                                    "efficient": {"2009": 72, "2010": 72}}},
                            "energy": {
                                "total": {
                                    "baseline": {"2009": 80, "2010": 80},
                                    "efficient": {"2009": 48, "2010": 48}},
                                "competed": {
                                    "baseline": {"2009": 40, "2010": 40},
                                    "efficient": {"2009": 8, "2010": 8}}},
                            "carbon": {
                                "total": {
                                    "baseline": {"2009": 120, "2010": 120},
                                    "efficient": {"2009": 72, "2010": 72}},
                                "competed": {
                                    "baseline": {"2009": 60, "2010": 60},
                                    "efficient": {"2009": 12, "2010": 12}}}},
                        "lifetime": {
                            "baseline": {"2009": 5, "2010": 5},
                            "measure": 10}},
                    "mseg_adjust": {
                        "contributing mseg keys and values": {
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'natural gas', 'water heating', None, 'new')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 10, "2010": 10},
                                        "measure": {"2009": 6, "2010": 6}},
                                    "competed": {
                                        "all": {"2009": 5, "2010": 5},
                                        "measure": {"2009": 1, "2010": 1}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 20, "2010": 20},
                                        "efficient": {"2009": 12, "2010": 12}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 2, "2010": 2}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 30, "2010": 30},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 15, "2010": 15},
                                        "efficient": {"2009": 3, "2010": 3}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 18, "2010": 18}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 18, "2010": 18}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 20, "2010": 20},
                                            "efficient": {
                                                "2009": 12, "2010": 12}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 2, "2010": 2}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 30, "2010": 30},
                                            "efficient": {
                                                "2009": 18, "2010": 18}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 15, "2010": 15},
                                            "efficient": {
                                                "2009": 3, "2010": 3}}}},
                                "lifetime": {
                                    "baseline": {"2009": 5, "2010": 5},
                                    "measure": 10},
                                "sub-market scaling": 1},
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'natural gas', 'water heating', None, "
                             "'existing')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 10, "2010": 10},
                                        "measure": {"2009": 6, "2010": 6}},
                                    "competed": {
                                        "all": {"2009": 5, "2010": 5},
                                        "measure": {"2009": 1, "2010": 1}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 20, "2010": 20},
                                        "efficient": {"2009": 12, "2010": 12}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 2, "2010": 2}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 30, "2010": 30},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 15, "2010": 15},
                                        "efficient": {"2009": 3, "2010": 3}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 18, "2010": 18}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 18, "2010": 18}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 20, "2010": 20},
                                            "efficient": {
                                                "2009": 12, "2010": 12}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 2, "2010": 2}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 30, "2010": 30},
                                            "efficient": {
                                                "2009": 18, "2010": 18}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 15, "2010": 15},
                                            "efficient": {
                                                "2009": 3, "2010": 3}}}},
                                "lifetime": {
                                    "baseline": {"2009": 5, "2010": 5},
                                    "measure": 10},
                                "sub-market scaling": 1},
                            ("('primary', AIA_CZ2', 'single family home', "
                             "'natural gas', 'water heating', None, 'new')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 10, "2010": 10},
                                        "measure": {"2009": 6, "2010": 6}},
                                    "competed": {
                                        "all": {"2009": 5, "2010": 5},
                                        "measure": {"2009": 1, "2010": 1}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 20, "2010": 20},
                                        "efficient": {"2009": 12, "2010": 12}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 2, "2010": 2}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 30, "2010": 30},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 15, "2010": 15},
                                        "efficient": {"2009": 3, "2010": 3}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 18, "2010": 18}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 18, "2010": 18}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 20, "2010": 20},
                                            "efficient": {
                                                "2009": 12, "2010": 12}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 2, "2010": 2}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 30, "2010": 30},
                                            "efficient": {
                                                "2009": 18, "2010": 18}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 15, "2010": 15},
                                            "efficient": {
                                                "2009": 3, "2010": 3}}}},
                                "lifetime": {
                                    "baseline": {"2009": 5, "2010": 5},
                                    "measure": 10},
                                "sub-market scaling": 1},
                            ("('primary', AIA_CZ2', 'single family home', "
                             "'natural gas', 'water heating', None, "
                             "'existing')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 10, "2010": 10},
                                        "measure": {"2009": 6, "2010": 6}},
                                    "competed": {
                                        "all": {"2009": 5, "2010": 5},
                                        "measure": {"2009": 1, "2010": 1}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 20, "2010": 20},
                                        "efficient": {"2009": 12, "2010": 12}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 2, "2010": 2}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 30, "2010": 30},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 15, "2010": 15},
                                        "efficient": {"2009": 3, "2010": 3}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 18, "2010": 18}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 18, "2010": 18}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 20, "2010": 20},
                                            "efficient": {
                                                "2009": 12, "2010": 12}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 2, "2010": 2}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 30, "2010": 30},
                                            "efficient": {
                                                "2009": 18, "2010": 18}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 15, "2010": 15},
                                            "efficient": {
                                                "2009": 3, "2010": 3}}}},
                                "lifetime": {
                                    "baseline": {"2009": 5, "2010": 5},
                                    "measure": 10},
                                "sub-market scaling": 1}},
                        "competed choice parameters": {
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'natural gas', 'water heating', None, 'new')"): {
                                "b1": {"2009": 0.5, "2010": 0.5},
                                "b2": {"2009": 0.5, "2010": 0.5}},
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'natural gas', 'water heating', None, "
                             "'existing')"): {
                                "b1": {"2009": 0.5, "2010": 0.5},
                                "b2": {"2009": 0.5, "2010": 0.5}},
                            ("('primary', AIA_CZ2', 'single family home', "
                             "'natural gas', 'water heating', None, 'new')"): {
                                "b1": {"2009": 0.5, "2010": 0.5},
                                "b2": {"2009": 0.5, "2010": 0.5}},
                            ("('primary', AIA_CZ2', 'single family home', "
                             "'natural gas', 'water heating', None, "
                             "'existing')"): {
                                "b1": {"2009": 0.5, "2010": 0.5},
                                "b2": {"2009": 0.5, "2010": 0.5}}},
                        "secondary mseg adjustments": {
                            "sub-market": {
                                "original energy (total)": {},
                                "adjusted energy (sub-market)": {}},
                            "stock-and-flow": {
                                "original energy (total)": {},
                                "adjusted energy (previously captured)": {},
                                "adjusted energy (competed)": {},
                                "adjusted energy (competed and captured)": {}},
                            "market share": {
                                "original energy (total captured)": {},
                                "original energy (competed and captured)": {},
                                "adjusted energy (total captured)": {},
                                "adjusted energy (competed and captured)": {}}}
                                },
                    "mseg_out_break": {
                        'AIA CZ1': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {
                                    "2009": 0.5, "2010": 0.5},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {
                                    "2009": 0, "2010": 0},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}}},
                        'AIA CZ2': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {
                                    "2009": 0.5, "2010": 0.5},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {
                                    "2009": 0, "2010": 0},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}}},
                        'AIA CZ3': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ4': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ5': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}}}},
                "Max adoption potential": {
                    "master_mseg": {
                        "stock": {
                            "total": {
                                "all": {"2009": 40, "2010": 40},
                                "measure": {"2009": 24, "2010": 24}},
                            "competed": {
                                "all": {"2009": 20, "2010": 20},
                                "measure": {"2009": 4, "2010": 4}}},
                        "energy": {
                            "total": {
                                "baseline": {"2009": 80, "2010": 80},
                                "efficient": {"2009": 48, "2010": 48}},
                            "competed": {
                                "baseline": {"2009": 40, "2010": 40},
                                "efficient": {"2009": 8, "2010": 8}}},
                        "carbon": {
                            "total": {
                                "baseline": {"2009": 120, "2010": 120},
                                "efficient": {"2009": 72, "2010": 72}},
                            "competed": {
                                "baseline": {"2009": 60, "2010": 60},
                                "efficient": {"2009": 12, "2010": 12}}},
                        "cost": {
                            "stock": {
                                "total": {
                                    "baseline": {"2009": 40, "2010": 40},
                                    "efficient": {"2009": 72, "2010": 72}},
                                "competed": {
                                    "baseline": {"2009": 40, "2010": 40},
                                    "efficient": {"2009": 72, "2010": 72}}},
                            "energy": {
                                "total": {
                                    "baseline": {"2009": 80, "2010": 80},
                                    "efficient": {"2009": 48, "2010": 48}},
                                "competed": {
                                    "baseline": {"2009": 40, "2010": 40},
                                    "efficient": {"2009": 8, "2010": 8}}},
                            "carbon": {
                                "total": {
                                    "baseline": {"2009": 120, "2010": 120},
                                    "efficient": {"2009": 72, "2010": 72}},
                                "competed": {
                                    "baseline": {"2009": 60, "2010": 60},
                                    "efficient": {"2009": 12, "2010": 12}}}},
                        "lifetime": {
                            "baseline": {"2009": 5, "2010": 5},
                            "measure": 10}},
                    "mseg_adjust": {
                        "contributing mseg keys and values": {
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'natural gas', 'water heating', None, 'new')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 10, "2010": 10},
                                        "measure": {"2009": 6, "2010": 6}},
                                    "competed": {
                                        "all": {"2009": 5, "2010": 5},
                                        "measure": {"2009": 1, "2010": 1}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 20, "2010": 20},
                                        "efficient": {"2009": 12, "2010": 12}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 2, "2010": 2}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 30, "2010": 30},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 15, "2010": 15},
                                        "efficient": {"2009": 3, "2010": 3}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 18, "2010": 18}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 18, "2010": 18}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 20, "2010": 20},
                                            "efficient": {
                                                "2009": 12, "2010": 12}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 2, "2010": 2}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 30, "2010": 30},
                                            "efficient": {
                                                "2009": 18, "2010": 18}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 15, "2010": 15},
                                            "efficient": {
                                                "2009": 3, "2010": 3}}}},
                                "lifetime": {
                                    "baseline": {"2009": 5, "2010": 5},
                                    "measure": 10},
                                "sub-market scaling": 1},
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'natural gas', 'water heating', None, "
                             "'existing')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 10, "2010": 10},
                                        "measure": {"2009": 6, "2010": 6}},
                                    "competed": {
                                        "all": {"2009": 5, "2010": 5},
                                        "measure": {"2009": 1, "2010": 1}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 20, "2010": 20},
                                        "efficient": {"2009": 12, "2010": 12}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 2, "2010": 2}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 30, "2010": 30},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 15, "2010": 15},
                                        "efficient": {"2009": 3, "2010": 3}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 18, "2010": 18}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 18, "2010": 18}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 20, "2010": 20},
                                            "efficient": {
                                                "2009": 12, "2010": 12}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 2, "2010": 2}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 30, "2010": 30},
                                            "efficient": {
                                                "2009": 18, "2010": 18}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 15, "2010": 15},
                                            "efficient": {
                                                "2009": 3, "2010": 3}}}},
                                "lifetime": {
                                    "baseline": {"2009": 5, "2010": 5},
                                    "measure": 10},
                                "sub-market scaling": 1},
                            ("('primary', AIA_CZ2', 'single family home', "
                             "'natural gas', 'water heating', None, 'new')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 10, "2010": 10},
                                        "measure": {"2009": 6, "2010": 6}},
                                    "competed": {
                                        "all": {"2009": 5, "2010": 5},
                                        "measure": {"2009": 1, "2010": 1}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 20, "2010": 20},
                                        "efficient": {"2009": 12, "2010": 12}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 2, "2010": 2}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 30, "2010": 30},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 15, "2010": 15},
                                        "efficient": {"2009": 3, "2010": 3}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 18, "2010": 18}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 18, "2010": 18}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 20, "2010": 20},
                                            "efficient": {
                                                "2009": 12, "2010": 12}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 2, "2010": 2}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 30, "2010": 30},
                                            "efficient": {
                                                "2009": 18, "2010": 18}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 15, "2010": 15},
                                            "efficient": {
                                                "2009": 3, "2010": 3}}}},
                                "lifetime": {
                                    "baseline": {"2009": 5, "2010": 5},
                                    "measure": 10},
                                "sub-market scaling": 1},
                            ("('primary', AIA_CZ2', 'single family home', "
                             "'natural gas', 'water heating', None, "
                             "'existing')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 10, "2010": 10},
                                        "measure": {"2009": 6, "2010": 6}},
                                    "competed": {
                                        "all": {"2009": 5, "2010": 5},
                                        "measure": {"2009": 1, "2010": 1}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 20, "2010": 20},
                                        "efficient": {"2009": 12, "2010": 12}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 2, "2010": 2}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 30, "2010": 30},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 15, "2010": 15},
                                        "efficient": {"2009": 3, "2010": 3}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 18, "2010": 18}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 18, "2010": 18}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 20, "2010": 20},
                                            "efficient": {
                                                "2009": 12, "2010": 12}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 10, "2010": 10},
                                            "efficient": {
                                                "2009": 2, "2010": 2}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 30, "2010": 30},
                                            "efficient": {
                                                "2009": 18, "2010": 18}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 15, "2010": 15},
                                            "efficient": {
                                                "2009": 3, "2010": 3}}}},
                                "lifetime": {
                                    "baseline": {"2009": 5, "2010": 5},
                                    "measure": 10},
                                "sub-market scaling": 1}},
                        "competed choice parameters": {
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'natural gas', 'water heating', None, 'new')"): {
                                "b1": {"2009": 0.5, "2010": 0.5},
                                "b2": {"2009": 0.5, "2010": 0.5}},
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'natural gas', 'water heating', None, "
                             "'existing')"): {
                                "b1": {"2009": 0.5, "2010": 0.5},
                                "b2": {"2009": 0.5, "2010": 0.5}},
                            ("('primary', AIA_CZ2', 'single family home', "
                             "'natural gas', 'water heating', None, 'new')"): {
                                "b1": {"2009": 0.5, "2010": 0.5},
                                "b2": {"2009": 0.5, "2010": 0.5}},
                            ("('primary', AIA_CZ2', 'single family home', "
                             "'natural gas', 'water heating', None, "
                             "'existing')"): {
                                "b1": {"2009": 0.5, "2010": 0.5},
                                "b2": {"2009": 0.5, "2010": 0.5}}},
                        "secondary mseg adjustments": {
                            "sub-market": {
                                "original energy (total)": {},
                                "adjusted energy (sub-market)": {}},
                            "stock-and-flow": {
                                "original energy (total)": {},
                                "adjusted energy (previously captured)": {},
                                "adjusted energy (competed)": {},
                                "adjusted energy (competed and captured)": {}},
                            "market share": {
                                "original energy (total captured)": {},
                                "original energy (competed and captured)": {},
                                "adjusted energy (total captured)": {},
                                "adjusted energy (competed and captured)": {}}}
                                },
                    "mseg_out_break": {
                        'AIA CZ1': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {
                                    "2009": 0.5, "2010": 0.5},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {
                                    "2009": 0, "2010": 0},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}}},
                        'AIA CZ2': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {
                                    "2009": 0.5, "2010": 0.5},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {
                                    "2009": 0, "2010": 0},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}}},
                        'AIA CZ3': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ4': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ5': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}}}}},
            "out_break_norm": {
                "Technical potential": {"2009": 80, "2010": 80},
                "Max adoption potential": {"2009": 80, "2010": 80}}},
            {
            "name": "sample measure pkg 2",
            "market_entry_year": None,
            "market_exit_year": None,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["existing"],
            "climate_zone": ["AIA_CZ1"],
            "bldg_type": ["single family home"],
            "fuel_type": ["electricity"],
            "fuel_switch_to": None,
            "end_use": {"primary": ["lighting"],
                        "secondary": None},
            "technology": [
                "reflector (incandescent)",
                "reflector (halogen)"],
            "technology_type": {
                "primary": "supply", "secondary": None},
            "markets": {
                "Technical potential": {
                    "master_mseg": {
                        "stock": {
                            "total": {
                                "all": {"2009": 200, "2010": 200},
                                "measure": {"2009": 120, "2010": 120}},
                            "competed": {
                                "all": {"2009": 100, "2010": 100},
                                "measure": {"2009": 20, "2010": 20}}},
                        "energy": {
                            "total": {
                                "baseline": {"2009": 400, "2010": 400},
                                "efficient": {"2009": 240, "2010": 240}},
                            "competed": {
                                "baseline": {"2009": 200, "2010": 200},
                                "efficient": {"2009": 40, "2010": 40}}},
                        "carbon": {
                            "total": {
                                "baseline": {"2009": 600, "2010": 600},
                                "efficient": {"2009": 360, "2010": 360}},
                            "competed": {
                                "baseline": {"2009": 300, "2010": 300},
                                "efficient": {"2009": 60, "2010": 60}}},
                        "cost": {
                            "stock": {
                                "total": {
                                    "baseline": {"2009": 200, "2010": 200},
                                    "efficient": {"2009": 360, "2010": 360}},
                                "competed": {
                                    "baseline": {"2009": 200, "2010": 200},
                                    "efficient": {"2009": 360, "2010": 360}}},
                            "energy": {
                                "total": {
                                    "baseline": {"2009": 400, "2010": 400},
                                    "efficient": {"2009": 240, "2010": 240}},
                                "competed": {
                                    "baseline": {"2009": 200, "2010": 200},
                                    "efficient": {"2009": 40, "2010": 40}}},
                            "carbon": {
                                "total": {
                                    "baseline": {"2009": 600, "2010": 600},
                                    "efficient": {"2009": 360, "2010": 360}},
                                "competed": {
                                    "baseline": {"2009": 300, "2010": 300},
                                    "efficient": {"2009": 60, "2010": 60}}}},
                        "lifetime": {
                            "baseline": {"2009": 1, "2010": 1},
                            "measure": 20}},
                    "mseg_adjust": {
                        "contributing mseg keys and values": {
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'electricity',"
                             "'lighting', 'reflector (incandescent)', "
                             "'existing')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 100, "2010": 100},
                                        "measure": {"2009": 60, "2010": 60}},
                                    "competed": {
                                        "all": {"2009": 50, "2010": 50},
                                        "measure": {"2009": 10, "2010": 10}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 200, "2010": 200},
                                        "efficient": {
                                            "2009": 120, "2010": 120}},
                                    "competed": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 20, "2010": 20}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 300, "2010": 300},
                                        "efficient": {
                                            "2009": 180, "2010": 180}},
                                    "competed": {
                                        "baseline": {"2009": 150, "2010": 150},
                                        "efficient": {
                                            "2009": 30, "2010": 30}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 200, "2010": 200},
                                            "efficient": {
                                                "2009": 120, "2010": 120}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 20, "2010": 20}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 300, "2010": 300},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 150, "2010": 150},
                                            "efficient": {
                                                "2009": 30, "2010": 30}}}},
                                "lifetime": {
                                    "baseline": {"2009": 1, "2010": 1},
                                    "measure": 20},
                                "sub-market scaling": 1},
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'electricity',"
                             "'lighting', 'reflector (halogen)', "
                             "'existing')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 100, "2010": 100},
                                        "measure": {"2009": 60, "2010": 60}},
                                    "competed": {
                                        "all": {"2009": 50, "2010": 50},
                                        "measure": {"2009": 10, "2010": 10}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 200, "2010": 200},
                                        "efficient": {
                                            "2009": 120, "2010": 120}},
                                    "competed": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 20, "2010": 20}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 300, "2010": 300},
                                        "efficient": {
                                            "2009": 180, "2010": 180}},
                                    "competed": {
                                        "baseline": {"2009": 150, "2010": 150},
                                        "efficient": {
                                            "2009": 30, "2010": 30}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 200, "2010": 200},
                                            "efficient": {
                                                "2009": 120, "2010": 120}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 20, "2010": 20}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 300, "2010": 300},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 150, "2010": 150},
                                            "efficient": {
                                                "2009": 30, "2010": 30}}}},
                                "lifetime": {
                                    "baseline": {"2009": 2, "2010": 2},
                                    "measure": 15},
                                "sub-market scaling": 1}},
                        "competed choice parameters": {
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'electricity',"
                             "'lighting', 'reflector (incandescent)', "
                             "'existing')"): {
                                "b1": {"2009": 0.25, "2010": 0.25},
                                "b2": {"2009": 0.25, "2010": 0.25}},
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'electricity',"
                             "'lighting', 'reflector (halogen)', "
                             "'existing')"): {
                                "b1": {"2009": 0.25, "2010": 0.25},
                                "b2": {"2009": 0.25, "2010": 0.25}}},
                        "secondary mseg adjustments": {
                            "sub-market": {
                                "original energy (total)": {},
                                "adjusted energy (sub-market)": {}},
                            "stock-and-flow": {
                                "original energy (total)": {},
                                "adjusted energy (previously captured)": {},
                                "adjusted energy (competed)": {},
                                "adjusted energy (competed and captured)": {}},
                            "market share": {
                                "original energy (total captured)": {},
                                "original energy (competed and captured)": {},
                                "adjusted energy (total captured)": {},
                                "adjusted energy (competed and captured)": {}}}
                                },
                    "mseg_out_break": {
                        'AIA CZ1': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {
                                    "2009": 1, "2010": 1},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ2': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ3': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ4': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ5': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}}}},
                "Max adoption potential": {
                    "master_mseg": {
                        "stock": {
                            "total": {
                                "all": {"2009": 200, "2010": 200},
                                "measure": {"2009": 120, "2010": 120}},
                            "competed": {
                                "all": {"2009": 100, "2010": 100},
                                "measure": {"2009": 20, "2010": 20}}},
                        "energy": {
                            "total": {
                                "baseline": {"2009": 400, "2010": 400},
                                "efficient": {"2009": 240, "2010": 240}},
                            "competed": {
                                "baseline": {"2009": 200, "2010": 200},
                                "efficient": {"2009": 40, "2010": 40}}},
                        "carbon": {
                            "total": {
                                "baseline": {"2009": 600, "2010": 600},
                                "efficient": {"2009": 360, "2010": 360}},
                            "competed": {
                                "baseline": {"2009": 300, "2010": 300},
                                "efficient": {"2009": 60, "2010": 60}}},
                        "cost": {
                            "stock": {
                                "total": {
                                    "baseline": {"2009": 200, "2010": 200},
                                    "efficient": {"2009": 360, "2010": 360}},
                                "competed": {
                                    "baseline": {"2009": 200, "2010": 200},
                                    "efficient": {"2009": 360, "2010": 360}}},
                            "energy": {
                                "total": {
                                    "baseline": {"2009": 400, "2010": 400},
                                    "efficient": {"2009": 240, "2010": 240}},
                                "competed": {
                                    "baseline": {"2009": 200, "2010": 200},
                                    "efficient": {"2009": 40, "2010": 40}}},
                            "carbon": {
                                "total": {
                                    "baseline": {"2009": 600, "2010": 600},
                                    "efficient": {"2009": 360, "2010": 360}},
                                "competed": {
                                    "baseline": {"2009": 300, "2010": 300},
                                    "efficient": {"2009": 60, "2010": 60}}}},
                        "lifetime": {
                            "baseline": {"2009": 1, "2010": 1},
                            "measure": 20}},
                    "mseg_adjust": {
                        "contributing mseg keys and values": {
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'electricity',"
                             "'lighting', 'reflector (incandescent)', "
                             "'existing')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 100, "2010": 100},
                                        "measure": {"2009": 60, "2010": 60}},
                                    "competed": {
                                        "all": {"2009": 50, "2010": 50},
                                        "measure": {"2009": 10, "2010": 10}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 200, "2010": 200},
                                        "efficient": {
                                            "2009": 120, "2010": 120}},
                                    "competed": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 20, "2010": 20}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 300, "2010": 300},
                                        "efficient": {
                                            "2009": 180, "2010": 180}},
                                    "competed": {
                                        "baseline": {"2009": 150, "2010": 150},
                                        "efficient": {
                                            "2009": 30, "2010": 30}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 200, "2010": 200},
                                            "efficient": {
                                                "2009": 120, "2010": 120}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 20, "2010": 20}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 300, "2010": 300},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 150, "2010": 150},
                                            "efficient": {
                                                "2009": 30, "2010": 30}}}},
                                "lifetime": {
                                    "baseline": {"2009": 1, "2010": 1},
                                    "measure": 20},
                                "sub-market scaling": 1},
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'electricity',"
                             "'lighting', 'reflector (halogen)', "
                             "'existing')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 100, "2010": 100},
                                        "measure": {"2009": 60, "2010": 60}},
                                    "competed": {
                                        "all": {"2009": 50, "2010": 50},
                                        "measure": {"2009": 10, "2010": 10}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 200, "2010": 200},
                                        "efficient": {
                                            "2009": 120, "2010": 120}},
                                    "competed": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 20, "2010": 20}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 300, "2010": 300},
                                        "efficient": {
                                            "2009": 180, "2010": 180}},
                                    "competed": {
                                        "baseline": {"2009": 150, "2010": 150},
                                        "efficient": {
                                            "2009": 30, "2010": 30}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 200, "2010": 200},
                                            "efficient": {
                                                "2009": 120, "2010": 120}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 20, "2010": 20}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 300, "2010": 300},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 150, "2010": 150},
                                            "efficient": {
                                                "2009": 30, "2010": 30}}}},
                                "lifetime": {
                                    "baseline": {"2009": 2, "2010": 2},
                                    "measure": 15},
                                "sub-market scaling": 1}},
                        "competed choice parameters": {
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'electricity',"
                             "'lighting', 'reflector (incandescent)', "
                             "'existing')"): {
                                "b1": {"2009": 0.25, "2010": 0.25},
                                "b2": {"2009": 0.25, "2010": 0.25}},
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'electricity',"
                             "'lighting', 'reflector (halogen)', "
                             "'existing')"): {
                                "b1": {"2009": 0.25, "2010": 0.25},
                                "b2": {"2009": 0.25, "2010": 0.25}}},
                        "secondary mseg adjustments": {
                            "sub-market": {
                                "original energy (total)": {},
                                "adjusted energy (sub-market)": {}},
                            "stock-and-flow": {
                                "original energy (total)": {},
                                "adjusted energy (previously captured)": {},
                                "adjusted energy (competed)": {},
                                "adjusted energy (competed and captured)": {}},
                            "market share": {
                                "original energy (total captured)": {},
                                "original energy (competed and captured)": {},
                                "adjusted energy (total captured)": {},
                                "adjusted energy (competed and captured)": {}}}
                                },
                    "mseg_out_break": {
                        'AIA CZ1': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {
                                    "2009": 1, "2010": 1},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ2': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ3': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ4': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ5': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}}}}},
            "out_break_norm": {
                "Technical potential": {"2009": 400, "2010": 400},
                "Max adoption potential": {"2009": 400, "2010": 400}}},
            {
            "name": "sample measure pkg 3",
            "market_entry_year": None,
            "market_exit_year": None,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "full service",
            "structure_type": ["new", "existing"],
            "climate_zone": ["AIA_CZ1", "AIA_CZ5"],
            "bldg_type": ["multi family home"],
            "fuel_type": ["electricity"],
            "fuel_switch_to": None,
            "end_use": {
                "primary": ["cooling", "lighting"],
                "secondary": None},
            "technology": [
                    "ASHP",
                    "reflector (incandescent)"],
            "technology_type": {
                "primary": "supply", "secondary": None},
            "markets": {
                "Technical potential": {
                    "master_mseg": {
                        "stock": {
                            "total": {
                                "all": {"2009": 1100, "2010": 1100},
                                "measure": {"2009": 660, "2010": 660}},
                            "competed": {
                                "all": {"2009": 550, "2010": 550},
                                "measure": {"2009": 110, "2010": 110}}},
                        "energy": {
                            "total": {
                                "baseline": {"2009": 2200, "2010": 2200},
                                "efficient": {"2009": 1320, "2010": 1320}},
                            "competed": {
                                "baseline": {"2009": 1100, "2010": 1100},
                                "efficient": {"2009": 220, "2010": 220}}},
                        "carbon": {
                            "total": {
                                "baseline": {"2009": 3300, "2010": 3300},
                                "efficient": {"2009": 1980, "2010": 1980}},
                            "competed": {
                                "baseline": {"2009": 1650, "2010": 1650},
                                "efficient": {"2009": 330, "2010": 330}}},
                        "cost": {
                            "stock": {
                                "total": {
                                    "baseline": {"2009": 200, "2010": 200},
                                    "efficient": {"2009": 360, "2010": 360}},
                                "competed": {
                                    "baseline": {"2009": 200, "2010": 200},
                                    "efficient": {"2009": 360, "2010": 360}}},
                            "energy": {
                                "total": {
                                    "baseline": {"2009": 400, "2010": 400},
                                    "efficient": {"2009": 240, "2010": 240}},
                                "competed": {
                                    "baseline": {"2009": 200, "2010": 200},
                                    "efficient": {"2009": 40, "2010": 40}}},
                            "carbon": {
                                "total": {
                                    "baseline": {"2009": 600, "2010": 600},
                                    "efficient": {"2009": 360, "2010": 360}},
                                "competed": {
                                    "baseline": {"2009": 300, "2010": 300},
                                    "efficient": {"2009": 60, "2010": 60}}}},
                        "lifetime": {
                            "baseline": {"2009": 18, "2010": 18},
                            "measure": 18}},
                    "mseg_adjust": {
                        "contributing mseg keys and values": {
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'electricity',"
                             "'lighting', 'reflector (incandescent)', "
                             "'existing')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 100, "2010": 100},
                                        "measure": {"2009": 60, "2010": 60}},
                                    "competed": {
                                        "all": {"2009": 50, "2010": 50},
                                        "measure": {"2009": 10, "2010": 10}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 200, "2010": 200},
                                        "efficient": {
                                            "2009": 120, "2010": 120}},
                                    "competed": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 20, "2010": 20}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 300, "2010": 300},
                                        "efficient": {
                                            "2009": 180, "2010": 180}},
                                    "competed": {
                                        "baseline": {"2009": 150, "2010": 150},
                                        "efficient": {
                                            "2009": 30, "2010": 30}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 200, "2010": 200},
                                            "efficient": {
                                                "2009": 120, "2010": 120}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 20, "2010": 20}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 300, "2010": 300},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 150, "2010": 150},
                                            "efficient": {
                                                "2009": 30, "2010": 30}}}},
                                "lifetime": {
                                    "baseline": {"2009": 1, "2010": 1},
                                    "measure": 20},
                                "sub-market scaling": 1},
                            ("('primary', AIA_CZ5', 'single family home', "
                             "'electricity',"
                             "'cooling', 'supply', 'ASHP', 'new')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 1000, "2010": 1000},
                                        "measure": {"2009": 600, "2010": 600}},
                                    "competed": {
                                        "all": {"2009": 500, "2010": 500},
                                        "measure": {
                                            "2009": 100, "2010": 100}}},
                                "energy": {
                                    "total": {
                                        "baseline": {
                                            "2009": 2000, "2010": 2000},
                                        "efficient": {
                                            "2009": 1200, "2010": 1200}},
                                    "competed": {
                                        "baseline": {
                                            "2009": 1000, "2010": 1000},
                                        "efficient": {
                                            "2009": 200, "2010": 200}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {
                                            "2009": 3000, "2010": 3000},
                                        "efficient": {
                                            "2009": 1800, "2010": 1800}},
                                    "competed": {
                                        "baseline": {
                                            "2009": 1500, "2010": 1500},
                                        "efficient": {
                                            "2009": 300, "2010": 300}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 200, "2010": 200},
                                            "efficient": {
                                                "2009": 120, "2010": 120}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 20, "2010": 20}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 300, "2010": 300},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 150, "2010": 150},
                                            "efficient": {
                                                "2009": 30, "2010": 30}}}},
                                "lifetime": {
                                    "baseline": {"2009": 18, "2010": 18},
                                    "measure": 18},
                                "sub-market scaling": 1}},
                        "competed choice parameters": {
                            ("('primary', AIA_CZ5', 'single family home', "
                             "'electricity',"
                             "'cooling', 'supply', 'ASHP', 'new')"): {
                                "b1": {"2009": 0.75, "2010": 0.75},
                                "b2": {"2009": 0.75, "2010": 0.75}},
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'electricity',"
                             "'lighting', 'reflector (halogen)', "
                             "'existing')"): {
                                "b1": {"2009": 0.25, "2010": 0.25},
                                "b2": {"2009": 0.25, "2010": 0.25}}},
                        "secondary mseg adjustments": {
                            "sub-market": {
                                "original energy (total)": {},
                                "adjusted energy (sub-market)": {}},
                            "stock-and-flow": {
                                "original energy (total)": {},
                                "adjusted energy (previously captured)": {},
                                "adjusted energy (competed)": {},
                                "adjusted energy (competed and captured)": {}},
                            "market share": {
                                "original energy (total captured)": {},
                                "original energy (competed and captured)": {},
                                "adjusted energy (total captured)": {},
                                "adjusted energy (competed and captured)": {}}}
                                },
                    "mseg_out_break": {
                        'AIA CZ1': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {
                                    "2009": 0.5, "2010": 0.5},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ2': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ3': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ4': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ5': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {
                                    "2009": 0.5, "2010": 0.5},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}}}},
                "Max adoption potential": {
                    "master_mseg": {
                        "stock": {
                            "total": {
                                "all": {"2009": 1100, "2010": 1100},
                                "measure": {"2009": 660, "2010": 660}},
                            "competed": {
                                "all": {"2009": 550, "2010": 550},
                                "measure": {"2009": 110, "2010": 110}}},
                        "energy": {
                            "total": {
                                "baseline": {"2009": 2200, "2010": 2200},
                                "efficient": {"2009": 1320, "2010": 1320}},
                            "competed": {
                                "baseline": {"2009": 1100, "2010": 1100},
                                "efficient": {"2009": 220, "2010": 220}}},
                        "carbon": {
                            "total": {
                                "baseline": {"2009": 3300, "2010": 3300},
                                "efficient": {"2009": 1980, "2010": 1980}},
                            "competed": {
                                "baseline": {"2009": 1650, "2010": 1650},
                                "efficient": {"2009": 330, "2010": 330}}},
                        "cost": {
                            "stock": {
                                "total": {
                                    "baseline": {"2009": 200, "2010": 200},
                                    "efficient": {"2009": 360, "2010": 360}},
                                "competed": {
                                    "baseline": {"2009": 200, "2010": 200},
                                    "efficient": {"2009": 360, "2010": 360}}},
                            "energy": {
                                "total": {
                                    "baseline": {"2009": 400, "2010": 400},
                                    "efficient": {"2009": 240, "2010": 240}},
                                "competed": {
                                    "baseline": {"2009": 200, "2010": 200},
                                    "efficient": {"2009": 40, "2010": 40}}},
                            "carbon": {
                                "total": {
                                    "baseline": {"2009": 600, "2010": 600},
                                    "efficient": {"2009": 360, "2010": 360}},
                                "competed": {
                                    "baseline": {"2009": 300, "2010": 300},
                                    "efficient": {"2009": 60, "2010": 60}}}},
                        "lifetime": {
                            "baseline": {"2009": 18, "2010": 18},
                            "measure": 18}},
                    "mseg_adjust": {
                        "contributing mseg keys and values": {
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'electricity',"
                             "'lighting', 'reflector (incandescent)', "
                             "'existing')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 100, "2010": 100},
                                        "measure": {"2009": 60, "2010": 60}},
                                    "competed": {
                                        "all": {"2009": 50, "2010": 50},
                                        "measure": {"2009": 10, "2010": 10}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 200, "2010": 200},
                                        "efficient": {
                                            "2009": 120, "2010": 120}},
                                    "competed": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 20, "2010": 20}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 300, "2010": 300},
                                        "efficient": {
                                            "2009": 180, "2010": 180}},
                                    "competed": {
                                        "baseline": {"2009": 150, "2010": 150},
                                        "efficient": {
                                            "2009": 30, "2010": 30}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 200, "2010": 200},
                                            "efficient": {
                                                "2009": 120, "2010": 120}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 20, "2010": 20}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 300, "2010": 300},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 150, "2010": 150},
                                            "efficient": {
                                                "2009": 30, "2010": 30}}}},
                                "lifetime": {
                                    "baseline": {"2009": 1, "2010": 1},
                                    "measure": 20},
                                "sub-market scaling": 1},
                            ("('primary', AIA_CZ5', 'single family home', "
                             "'electricity',"
                             "'cooling', 'supply', 'ASHP', 'new')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 1000, "2010": 1000},
                                        "measure": {"2009": 600, "2010": 600}},
                                    "competed": {
                                        "all": {"2009": 500, "2010": 500},
                                        "measure": {
                                            "2009": 100, "2010": 100}}},
                                "energy": {
                                    "total": {
                                        "baseline": {
                                            "2009": 2000, "2010": 2000},
                                        "efficient": {
                                            "2009": 1200, "2010": 1200}},
                                    "competed": {
                                        "baseline": {
                                            "2009": 1000, "2010": 1000},
                                        "efficient": {
                                            "2009": 200, "2010": 200}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {
                                            "2009": 3000, "2010": 3000},
                                        "efficient": {
                                            "2009": 1800, "2010": 1800}},
                                    "competed": {
                                        "baseline": {
                                            "2009": 1500, "2010": 1500},
                                        "efficient": {
                                            "2009": 300, "2010": 300}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 200, "2010": 200},
                                            "efficient": {
                                                "2009": 120, "2010": 120}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 20, "2010": 20}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 300, "2010": 300},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 150, "2010": 150},
                                            "efficient": {
                                                "2009": 30, "2010": 30}}}},
                                "lifetime": {
                                    "baseline": {"2009": 18, "2010": 18},
                                    "measure": 18},
                                "sub-market scaling": 1}},
                        "competed choice parameters": {
                            ("('primary', AIA_CZ5', 'single family home', "
                             "'electricity',"
                             "'cooling', 'supply', 'ASHP', 'new')"): {
                                "b1": {"2009": 0.75, "2010": 0.75},
                                "b2": {"2009": 0.75, "2010": 0.75}},
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'electricity',"
                             "'lighting', 'reflector (halogen)', "
                             "'existing')"): {
                                "b1": {"2009": 0.25, "2010": 0.25},
                                "b2": {"2009": 0.25, "2010": 0.25}}},
                        "secondary mseg adjustments": {
                            "sub-market": {
                                "original energy (total)": {},
                                "adjusted energy (sub-market)": {}},
                            "stock-and-flow": {
                                "original energy (total)": {},
                                "adjusted energy (previously captured)": {},
                                "adjusted energy (competed)": {},
                                "adjusted energy (competed and captured)": {}},
                            "market share": {
                                "original energy (total captured)": {},
                                "original energy (competed and captured)": {},
                                "adjusted energy (total captured)": {},
                                "adjusted energy (competed and captured)": {}}}
                                },
                    "mseg_out_break": {
                        'AIA CZ1': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {
                                    "2009": 0.5, "2010": 0.5},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ2': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ3': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ4': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}},
                        'AIA CZ5': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {
                                    "2009": 0.5, "2010": 0.5},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {},
                                'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {},
                                'Envelope': {}}}}}},
            "out_break_norm": {
                "Technical potential": {"2009": 2200, "2010": 2200},
                "Max adoption potential": {"2009": 2200, "2010": 2200}}},
            {
            "name": "sample measure pkg 4",
            "market_entry_year": None,
            "market_exit_year": None,
            "market_scaling_fractions": None,
            "market_scaling_fractions_source": None,
            "measure_type": "add-on",
            "structure_type": ["existing"],
            "climate_zone": ["AIA_CZ1"],
            "bldg_type": ["single family home"],
            "fuel_type": ["electricity"],
            "fuel_switch_to": None,
            "end_use": {"primary": ["lighting"],
                        "secondary": None},
            "technology": [
                "reflector (incandescent)"],
            "technology_type": {
                "primary": "supply", "secondary": None},
            "markets": {
                "Technical potential": {
                    "master_mseg": {
                        "stock": {
                            "total": {
                                "all": {"2009": 100, "2010": 100},
                                "measure": {"2009": 60, "2010": 60}},
                            "competed": {
                                "all": {"2009": 50, "2010": 50},
                                "measure": {"2009": 10, "2010": 10}}},
                        "energy": {
                            "total": {
                                "baseline": {"2009": 200, "2010": 200},
                                "efficient": {
                                    "2009": 120, "2010": 120}},
                            "competed": {
                                "baseline": {"2009": 100, "2010": 100},
                                "efficient": {
                                    "2009": 20, "2010": 20}}},
                        "carbon": {
                            "total": {
                                "baseline": {"2009": 300, "2010": 300},
                                "efficient": {
                                    "2009": 180, "2010": 180}},
                            "competed": {
                                "baseline": {"2009": 150, "2010": 150},
                                "efficient": {
                                    "2009": 30, "2010": 30}}},
                        "cost": {
                            "stock": {
                                "total": {
                                    "baseline": {
                                        "2009": 100, "2010": 100},
                                    "efficient": {
                                        "2009": 180, "2010": 180}},
                                "competed": {
                                    "baseline": {
                                        "2009": 100, "2010": 100},
                                    "efficient": {
                                        "2009": 180, "2010": 180}}},
                            "energy": {
                                "total": {
                                    "baseline": {
                                        "2009": 200, "2010": 200},
                                    "efficient": {
                                        "2009": 120, "2010": 120}},
                                "competed": {
                                    "baseline": {
                                        "2009": 100, "2010": 100},
                                    "efficient": {
                                        "2009": 20, "2010": 20}}},
                            "carbon": {
                                "total": {
                                    "baseline": {
                                        "2009": 300, "2010": 300},
                                    "efficient": {
                                        "2009": 180, "2010": 180}},
                                "competed": {
                                    "baseline": {
                                        "2009": 150, "2010": 150},
                                    "efficient": {
                                        "2009": 30, "2010": 30}}}},
                        "lifetime": {
                            "baseline": {"2009": 1, "2010": 1},
                            "measure": 20}},
                    "mseg_adjust": {
                        "contributing mseg keys and values": {
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'electricity',"
                             "'lighting', 'reflector (incandescent)', "
                             "'existing')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 100, "2010": 100},
                                        "measure": {"2009": 60, "2010": 60}},
                                    "competed": {
                                        "all": {"2009": 50, "2010": 50},
                                        "measure": {"2009": 10, "2010": 10}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 200, "2010": 200},
                                        "efficient": {
                                            "2009": 120, "2010": 120}},
                                    "competed": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 20, "2010": 20}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 300, "2010": 300},
                                        "efficient": {
                                            "2009": 180, "2010": 180}},
                                    "competed": {
                                        "baseline": {"2009": 150, "2010": 150},
                                        "efficient": {
                                            "2009": 30, "2010": 30}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 200, "2010": 200},
                                            "efficient": {
                                                "2009": 120, "2010": 120}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 20, "2010": 20}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 300, "2010": 300},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 150, "2010": 150},
                                            "efficient": {
                                                "2009": 30, "2010": 30}}}},
                                "lifetime": {
                                    "baseline": {"2009": 1, "2010": 1},
                                    "measure": 20},
                                "sub-market scaling": 1}},
                        "competed choice parameters": {
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'electricity',"
                             "'lighting', 'reflector (incandescent)', "
                             "'existing')"): {
                                "b1": {"2009": 0.25, "2010": 0.25},
                                "b2": {"2009": 0.25, "2010": 0.25}}},
                        "secondary mseg adjustments": {
                            "sub-market": {
                                "original energy (total)": {},
                                "adjusted energy (sub-market)": {}},
                            "stock-and-flow": {
                                "original energy (total)": {},
                                "adjusted energy (previously captured)": {},
                                "adjusted energy (competed)": {},
                                "adjusted energy (competed and captured)": {}},
                            "market share": {
                                "original energy (total captured)": {},
                                "original energy (competed and captured)": {},
                                "adjusted energy (total captured)": {},
                                "adjusted energy (competed and captured)": {}}}
                                },
                    "mseg_out_break": {
                        'AIA CZ1': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {
                                    "2009": 1, "2010": 1},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}}},
                        'AIA CZ2': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}}},
                        'AIA CZ3': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}}},
                        'AIA CZ4': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}}},
                        'AIA CZ5': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}}}}},
                "Max adoption potential": {
                    "master_mseg": {
                        "stock": {
                            "total": {
                                "all": {"2009": 100, "2010": 100},
                                "measure": {"2009": 60, "2010": 60}},
                            "competed": {
                                "all": {"2009": 50, "2010": 50},
                                "measure": {"2009": 10, "2010": 10}}},
                        "energy": {
                            "total": {
                                "baseline": {"2009": 200, "2010": 200},
                                "efficient": {
                                    "2009": 120, "2010": 120}},
                            "competed": {
                                "baseline": {"2009": 100, "2010": 100},
                                "efficient": {
                                    "2009": 20, "2010": 20}}},
                        "carbon": {
                            "total": {
                                "baseline": {"2009": 300, "2010": 300},
                                "efficient": {
                                    "2009": 180, "2010": 180}},
                            "competed": {
                                "baseline": {"2009": 150, "2010": 150},
                                "efficient": {
                                    "2009": 30, "2010": 30}}},
                        "cost": {
                            "stock": {
                                "total": {
                                    "baseline": {
                                        "2009": 100, "2010": 100},
                                    "efficient": {
                                        "2009": 180, "2010": 180}},
                                "competed": {
                                    "baseline": {
                                        "2009": 100, "2010": 100},
                                    "efficient": {
                                        "2009": 180, "2010": 180}}},
                            "energy": {
                                "total": {
                                    "baseline": {
                                        "2009": 200, "2010": 200},
                                    "efficient": {
                                        "2009": 120, "2010": 120}},
                                "competed": {
                                    "baseline": {
                                        "2009": 100, "2010": 100},
                                    "efficient": {
                                        "2009": 20, "2010": 20}}},
                            "carbon": {
                                "total": {
                                    "baseline": {
                                        "2009": 300, "2010": 300},
                                    "efficient": {
                                        "2009": 180, "2010": 180}},
                                "competed": {
                                    "baseline": {
                                        "2009": 150, "2010": 150},
                                    "efficient": {
                                        "2009": 30, "2010": 30}}}},
                        "lifetime": {
                            "baseline": {"2009": 1, "2010": 1},
                            "measure": 20}},
                    "mseg_adjust": {
                        "contributing mseg keys and values": {
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'electricity',"
                             "'lighting', 'reflector (incandescent)', "
                             "'existing')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 100, "2010": 100},
                                        "measure": {"2009": 60, "2010": 60}},
                                    "competed": {
                                        "all": {"2009": 50, "2010": 50},
                                        "measure": {"2009": 10, "2010": 10}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 200, "2010": 200},
                                        "efficient": {
                                            "2009": 120, "2010": 120}},
                                    "competed": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 20, "2010": 20}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 300, "2010": 300},
                                        "efficient": {
                                            "2009": 180, "2010": 180}},
                                    "competed": {
                                        "baseline": {"2009": 150, "2010": 150},
                                        "efficient": {
                                            "2009": 30, "2010": 30}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 200, "2010": 200},
                                            "efficient": {
                                                "2009": 120, "2010": 120}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 20, "2010": 20}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 300, "2010": 300},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 150, "2010": 150},
                                            "efficient": {
                                                "2009": 30, "2010": 30}}}},
                                "lifetime": {
                                    "baseline": {"2009": 1, "2010": 1},
                                    "measure": 20},
                                "sub-market scaling": 1}},
                        "competed choice parameters": {
                            ("('primary', AIA_CZ1', 'single family home', "
                             "'electricity',"
                             "'lighting', 'reflector (incandescent)', "
                             "'existing')"): {
                                "b1": {"2009": 0.25, "2010": 0.25},
                                "b2": {"2009": 0.25, "2010": 0.25}}},
                        "secondary mseg adjustments": {
                            "sub-market": {
                                "original energy (total)": {},
                                "adjusted energy (sub-market)": {}},
                            "stock-and-flow": {
                                "original energy (total)": {},
                                "adjusted energy (previously captured)": {},
                                "adjusted energy (competed)": {},
                                "adjusted energy (competed and captured)": {}},
                            "market share": {
                                "original energy (total captured)": {},
                                "original energy (competed and captured)": {},
                                "adjusted energy (total captured)": {},
                                "adjusted energy (competed and captured)": {}}}},
                    "mseg_out_break": {
                        'AIA CZ1': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {
                                    "2009": 1, "2010": 1},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}}},
                        'AIA CZ2': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}}},
                        'AIA CZ3': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}}},
                        'AIA CZ4': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}}},
                        'AIA CZ5': {
                            'Residential (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Residential (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (New)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}},
                            'Commercial (Existing)': {
                                'Cooling (Equip.)': {}, 'Ventilation': {},
                                'Lighting': {},
                                'Refrigeration': {}, 'Other': {},
                                'Water Heating': {},
                                'Computers and Electronics': {},
                                'Heating (Equip.)': {}, 'Envelope': {}}}}}},
            "out_break_norm": {
                "Technical potential": {"2009": 200, "2010": 200},
                "Max adoption potential": {"2009": 200, "2010": 200}}}]
        cls.sample_measures_in = [ecm_prep.Measure(
            handyvars, **x) for x in sample_measures_in]
        # Reset sample measure technology types (initialized as string)
        for ind, m in enumerate(cls.sample_measures_in):
            m.technology_type = sample_measures_in[ind]["technology_type"]
        # Reset sample measure markets (initialized to None)
        for ind, m in enumerate(cls.sample_measures_in):
            m.markets = sample_measures_in[ind]["markets"]
        # Reset total absolute energy use figure used to normalize sample
        # measure energy savings summed by climate, building, and end use
        for ind, m in enumerate(cls.sample_measures_in):
            m.out_break_norm = sample_measures_in[ind]["out_break_norm"]
        cls.sample_package_name = "Package - CAC + CFLs + NGWH"
        cls.sample_package_in_test1 = ecm_prep.MeasurePackage(
            cls.sample_measures_in, cls.sample_package_name,
            benefits_test1, handyvars)
        cls.sample_package_in_test2 = ecm_prep.MeasurePackage(
            cls.sample_measures_in, cls.sample_package_name,
            benefits_test2, handyvars)
        cls.genattr_ok_out_test1 = [
            'Package - CAC + CFLs + NGWH',
            ['AIA_CZ1', 'AIA_CZ2', 'AIA_CZ5'],
            ['single family home', 'multi family home'],
            ['new', 'existing'],
            ['electricity', 'natural gas'],
            ['water heating', 'lighting', 'cooling']]
        cls.markets_ok_out_test1 = {
            "Technical potential": {
                "master_mseg": {
                    'stock': {
                        'total': {
                            'all': {'2009': 1240, '2010': 1240},
                            'measure': {'2009': 744, '2010': 744}},
                        'competed': {
                            'all': {'2009': 620, '2010': 620},
                            'measure': {'2009': 124, '2010': 124}}},
                    'energy': {
                        'total': {
                            'baseline': {'2009': 2480, '2010': 2480},
                            'efficient': {'2009': 1488, '2010': 1488}},
                        'competed': {
                            'baseline': {'2009': 1240, '2010': 1240},
                            'efficient': {'2009': 248, '2010': 248}}},
                    'carbon': {
                        'total': {
                            'baseline': {'2009': 3720, '2010': 3720},
                            'efficient': {'2009': 2232, '2010': 2232}},
                        'competed': {
                            'baseline': {'2009': 1860, '2010': 1860},
                            'efficient': {'2009': 372, '2010': 372}}},
                    'cost': {
                        'stock': {
                            'total': {
                                'baseline': {'2009': 340, '2010': 340},
                                'efficient': {'2009': 612, '2010': 612}},
                            'competed': {
                                'baseline': {'2009': 340, '2010': 340},
                                'efficient': {'2009': 612, '2010': 612}}},
                        'energy': {
                            'total': {
                                'baseline': {'2009': 680, '2010': 680},
                                'efficient': {'2009': 408, '2010': 408}},
                            'competed': {
                                'baseline': {'2009': 340, '2010': 340},
                                'efficient': {'2009': 68, '2010': 68}}},
                        'carbon': {
                            'total': {
                                'baseline': {'2009': 1020, '2010': 1020},
                                'efficient': {'2009': 612, '2010': 612}},
                            'competed': {
                                'baseline': {'2009': 510, '2010': 510},
                                'efficient': {'2009': 102, '2010': 102}}}},
                        "lifetime": {
                            "baseline": {'2010': (41 / 1240),
                                         '2009': (41 / 1240)},
                            "measure": 13.29}},
                "mseg_adjust": {
                    "contributing mseg keys and values": {
                        ("('primary', AIA_CZ1', 'single family home', "
                         "'natural gas', 'water heating', None, 'new')"): {
                            "stock": {
                                "total": {
                                    "all": {"2009": 10, "2010": 10},
                                    "measure": {"2009": 6, "2010": 6}},
                                "competed": {
                                    "all": {"2009": 5, "2010": 5},
                                    "measure": {"2009": 1, "2010": 1}}},
                            "energy": {
                                "total": {
                                    "baseline": {"2009": 20, "2010": 20},
                                    "efficient": {"2009": 12, "2010": 12}},
                                "competed": {
                                    "baseline": {"2009": 10, "2010": 10},
                                    "efficient": {"2009": 2, "2010": 2}}},
                            "carbon": {
                                "total": {
                                    "baseline": {"2009": 30, "2010": 30},
                                    "efficient": {"2009": 18, "2010": 18}},
                                "competed": {
                                    "baseline": {"2009": 15, "2010": 15},
                                    "efficient": {"2009": 3, "2010": 3}}},
                            "cost": {
                                "stock": {
                                    "total": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {
                                            "2009": 18, "2010": 18}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 20, "2010": 20},
                                        "efficient": {"2009": 12, "2010": 12}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 2, "2010": 2}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 30, "2010": 30},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 15, "2010": 15},
                                        "efficient": {"2009": 3, "2010": 3}}}},
                            "lifetime": {
                                "baseline": {"2009": 5, "2010": 5},
                                "measure": 10},
                            "sub-market scaling": 1},
                        ("('primary', AIA_CZ1', 'single family home', "
                         "'natural gas', 'water heating', None, "
                         "'existing')"): {
                            "stock": {
                                "total": {
                                    "all": {"2009": 10, "2010": 10},
                                    "measure": {"2009": 6, "2010": 6}},
                                "competed": {
                                    "all": {"2009": 5, "2010": 5},
                                    "measure": {"2009": 1, "2010": 1}}},
                            "energy": {
                                "total": {
                                    "baseline": {"2009": 20, "2010": 20},
                                    "efficient": {"2009": 12, "2010": 12}},
                                "competed": {
                                    "baseline": {"2009": 10, "2010": 10},
                                    "efficient": {"2009": 2, "2010": 2}}},
                            "carbon": {
                                "total": {
                                    "baseline": {"2009": 30, "2010": 30},
                                    "efficient": {"2009": 18, "2010": 18}},
                                "competed": {
                                    "baseline": {"2009": 15, "2010": 15},
                                    "efficient": {"2009": 3, "2010": 3}}},
                            "cost": {
                                "stock": {
                                    "total": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {
                                            "2009": 18, "2010": 18}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 20, "2010": 20},
                                        "efficient": {"2009": 12, "2010": 12}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 2, "2010": 2}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 30, "2010": 30},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 15, "2010": 15},
                                        "efficient": {"2009": 3, "2010": 3}}}},
                            "lifetime": {
                                "baseline": {"2009": 5, "2010": 5},
                                "measure": 10},
                            "sub-market scaling": 1},
                        ("('primary', AIA_CZ2', 'single family home', "
                         "'natural gas', 'water heating', None, 'new')"): {
                            "stock": {
                                "total": {
                                    "all": {"2009": 10, "2010": 10},
                                    "measure": {"2009": 6, "2010": 6}},
                                "competed": {
                                    "all": {"2009": 5, "2010": 5},
                                    "measure": {"2009": 1, "2010": 1}}},
                            "energy": {
                                "total": {
                                    "baseline": {"2009": 20, "2010": 20},
                                    "efficient": {"2009": 12, "2010": 12}},
                                "competed": {
                                    "baseline": {"2009": 10, "2010": 10},
                                    "efficient": {"2009": 2, "2010": 2}}},
                            "carbon": {
                                "total": {
                                    "baseline": {"2009": 30, "2010": 30},
                                    "efficient": {"2009": 18, "2010": 18}},
                                "competed": {
                                    "baseline": {"2009": 15, "2010": 15},
                                    "efficient": {"2009": 3, "2010": 3}}},
                            "cost": {
                                "stock": {
                                    "total": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {
                                            "2009": 18, "2010": 18}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 20, "2010": 20},
                                        "efficient": {"2009": 12, "2010": 12}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 2, "2010": 2}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 30, "2010": 30},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 15, "2010": 15},
                                        "efficient": {"2009": 3, "2010": 3}}}},
                            "lifetime": {
                                "baseline": {"2009": 5, "2010": 5},
                                "measure": 10},
                            "sub-market scaling": 1},
                        ("('primary', AIA_CZ2', 'single family home', "
                         "'natural gas', 'water heating', None, "
                         "'existing')"): {
                            "stock": {
                                "total": {
                                    "all": {"2009": 10, "2010": 10},
                                    "measure": {"2009": 6, "2010": 6}},
                                "competed": {
                                    "all": {"2009": 5, "2010": 5},
                                    "measure": {"2009": 1, "2010": 1}}},
                            "energy": {
                                "total": {
                                    "baseline": {"2009": 20, "2010": 20},
                                    "efficient": {"2009": 12, "2010": 12}},
                                "competed": {
                                    "baseline": {"2009": 10, "2010": 10},
                                    "efficient": {"2009": 2, "2010": 2}}},
                            "carbon": {
                                "total": {
                                    "baseline": {"2009": 30, "2010": 30},
                                    "efficient": {"2009": 18, "2010": 18}},
                                "competed": {
                                    "baseline": {"2009": 15, "2010": 15},
                                    "efficient": {"2009": 3, "2010": 3}}},
                            "cost": {
                                "stock": {
                                    "total": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {
                                            "2009": 18, "2010": 18}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 20, "2010": 20},
                                        "efficient": {"2009": 12, "2010": 12}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 2, "2010": 2}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 30, "2010": 30},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 15, "2010": 15},
                                        "efficient": {"2009": 3, "2010": 3}}}},
                            "lifetime": {
                                "baseline": {"2009": 5, "2010": 5},
                                "measure": 10},
                            "sub-market scaling": 1},
                        ("('primary', AIA_CZ1', 'single family home', "
                             "'electricity',"
                             "'lighting', 'reflector (incandescent)', "
                             "'existing')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 100, "2010": 100},
                                        "measure": {"2009": 60, "2010": 60}},
                                    "competed": {
                                        "all": {"2009": 50, "2010": 50},
                                        "measure": {"2009": 10, "2010": 10}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 200, "2010": 200},
                                        "efficient": {
                                            "2009": 120, "2010": 120}},
                                    "competed": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 20, "2010": 20}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 300, "2010": 300},
                                        "efficient": {
                                            "2009": 180, "2010": 180}},
                                    "competed": {
                                        "baseline": {"2009": 150, "2010": 150},
                                        "efficient": {
                                            "2009": 30, "2010": 30}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 200, "2010": 200},
                                            "efficient": {
                                                "2009": 120, "2010": 120}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 20, "2010": 20}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 300, "2010": 300},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 150, "2010": 150},
                                            "efficient": {
                                                "2009": 30, "2010": 30}}}},
                                "lifetime": {
                                    "baseline": {"2009": 1, "2010": 1},
                                    "measure": 20},
                                "sub-market scaling": 1},
                        ("('primary', AIA_CZ1', 'single family home', "
                         "'electricity',"
                         "'lighting', 'reflector (halogen)', 'existing')"): {
                            "stock": {
                                "total": {
                                    "all": {"2009": 100, "2010": 100},
                                    "measure": {"2009": 60, "2010": 60}},
                                "competed": {
                                    "all": {"2009": 50, "2010": 50},
                                    "measure": {"2009": 10, "2010": 10}}},
                            "energy": {
                                "total": {
                                    "baseline": {"2009": 200, "2010": 200},
                                    "efficient": {"2009": 120, "2010": 120}},
                                "competed": {
                                    "baseline": {"2009": 100, "2010": 100},
                                    "efficient": {"2009": 20, "2010": 20}}},
                            "carbon": {
                                "total": {
                                    "baseline": {"2009": 300, "2010": 300},
                                    "efficient": {"2009": 180, "2010": 180}},
                                "competed": {
                                    "baseline": {"2009": 150, "2010": 150},
                                    "efficient": {"2009": 30, "2010": 30}}},
                            "cost": {
                                "stock": {
                                    "total": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 180, "2010": 180}},
                                    "competed": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 180, "2010": 180}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 200, "2010": 200},
                                        "efficient": {
                                            "2009": 120, "2010": 120}},
                                    "competed": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 20, "2010": 20}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 300, "2010": 300},
                                        "efficient": {
                                            "2009": 180, "2010": 180}},
                                    "competed": {
                                        "baseline": {"2009": 150, "2010": 150},
                                        "efficient": {
                                            "2009": 30, "2010": 30}}}},
                            "lifetime": {
                                "baseline": {"2009": 2, "2010": 2},
                                "measure": 15},
                            "sub-market scaling": 1},
                        ("('primary', AIA_CZ5', 'single family home', "
                         "'electricity',"
                         "'cooling', 'supply', 'ASHP', 'new')"): {
                            "stock": {
                                "total": {
                                    "all": {"2009": 1000, "2010": 1000},
                                    "measure": {"2009": 600, "2010": 600}},
                                "competed": {
                                    "all": {"2009": 500, "2010": 500},
                                    "measure": {"2009": 100, "2010": 100}}},
                            "energy": {
                                "total": {
                                    "baseline": {"2009": 2000, "2010": 2000},
                                    "efficient": {"2009": 1200, "2010": 1200}},
                                "competed": {
                                    "baseline": {"2009": 1000, "2010": 1000},
                                    "efficient": {"2009": 200, "2010": 200}}},
                            "carbon": {
                                "total": {
                                    "baseline": {"2009": 3000, "2010": 3000},
                                    "efficient": {"2009": 1800, "2010": 1800}},
                                "competed": {
                                    "baseline": {"2009": 1500, "2010": 1500},
                                    "efficient": {"2009": 300, "2010": 300}}},
                            "cost": {
                                "stock": {
                                    "total": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 180, "2010": 180}},
                                    "competed": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 180, "2010": 180}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 200, "2010": 200},
                                        "efficient": {
                                            "2009": 120, "2010": 120}},
                                    "competed": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 20, "2010": 20}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 300, "2010": 300},
                                        "efficient": {
                                            "2009": 180, "2010": 180}},
                                    "competed": {
                                        "baseline": {"2009": 150, "2010": 150},
                                        "efficient": {
                                            "2009": 30, "2010": 30}}}},
                            "lifetime": {
                                "baseline": {"2009": 18, "2010": 18},
                                "measure": 18},
                            "sub-market scaling": 1}},
                    "competed choice parameters": {
                        ("('primary', AIA_CZ1', 'single family home', "
                         "'natural gas', 'water heating', None, 'new')"): {
                            "b1": {"2009": 0.5, "2010": 0.5},
                            "b2": {"2009": 0.5, "2010": 0.5}},
                        ("('primary', AIA_CZ1', 'single family home', "
                         "'natural gas', 'water heating', None, "
                         "'existing')"): {
                            "b1": {"2009": 0.5, "2010": 0.5},
                            "b2": {"2009": 0.5, "2010": 0.5}},
                        ("('primary', AIA_CZ2', 'single family home', "
                         "'natural gas', 'water heating', None, 'new')"): {
                            "b1": {"2009": 0.5, "2010": 0.5},
                            "b2": {"2009": 0.5, "2010": 0.5}},
                        ("('primary', AIA_CZ2', 'single family home', "
                         "'natural gas', 'water heating', None, "
                         "'existing')"): {
                            "b1": {"2009": 0.5, "2010": 0.5},
                            "b2": {"2009": 0.5, "2010": 0.5}},
                        ("('primary', AIA_CZ1', 'single family home', "
                         "'electricity',"
                         "'lighting', 'reflector (incandescent)', "
                         "'existing')"): {
                            "b1": {"2009": 0.25, "2010": 0.25},
                            "b2": {"2009": 0.25, "2010": 0.25}},
                        ("('primary', AIA_CZ1', 'single family home', "
                         "'electricity',"
                         "'lighting', 'reflector (halogen)', "
                         "'existing')"): {
                            "b1": {"2009": 0.25, "2010": 0.25},
                            "b2": {"2009": 0.25, "2010": 0.25}},
                        ("('primary', AIA_CZ5', 'single family home', "
                         "'electricity',"
                         "'cooling', 'supply', 'ASHP', 'new')"): {
                            "b1": {"2009": 0.75, "2010": 0.75},
                            "b2": {"2009": 0.75, "2010": 0.75}}},
                    "secondary mseg adjustments": {
                        "sub-market": {
                            "original energy (total)": {},
                            "adjusted energy (sub-market)": {}},
                        "stock-and-flow": {
                            "original energy (total)": {},
                            "adjusted energy (previously captured)": {},
                            "adjusted energy (competed)": {},
                            "adjusted energy (competed and captured)": {}},
                        "market share": {
                            "original energy (total captured)": {},
                            "original energy (competed and captured)": {},
                            "adjusted energy (total captured)": {},
                            "adjusted energy (competed and captured)": {}}}},
                "mseg_out_break": {
                    'AIA CZ1': {
                        'Residential (New)': {
                            'Cooling (Equip.)': {},
                            'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {"2009": 0.016, "2010": 0.016},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Residential (Existing)': {
                            'Cooling (Equip.)': {},
                            'Ventilation': {},
                            'Lighting': {
                                "2009": 0.5510753,
                                "2010": 0.5510753},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {"2009": 0, "2010": 0},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (New)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (Existing)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}}},
                    'AIA CZ2': {
                        'Residential (New)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {"2009": 0.016, "2010": 0.016},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Residential (Existing)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {"2009": 0, "2010": 0},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (New)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (Existing)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}}},
                    'AIA CZ3': {
                        'Residential (New)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Residential (Existing)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (New)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (Existing)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}}},
                    'AIA CZ4': {
                        'Residential (New)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Residential (Existing)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (New)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (Existing)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}}},
                    'AIA CZ5': {
                        'Residential (New)': {
                            'Cooling (Equip.)': {
                                "2009": 0.4166667, "2010": 0.4166667},
                            'Ventilation': {}, 'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Residential (Existing)': {
                            'Cooling (Equip.)': {},
                            'Ventilation': {}, 'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (New)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (Existing)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}}}}},
            "Max adoption potential": {
                "master_mseg": {
                    'stock': {
                        'total': {
                            'all': {'2009': 1240, '2010': 1240},
                            'measure': {'2009': 744, '2010': 744}},
                        'competed': {
                            'all': {'2009': 620, '2010': 620},
                            'measure': {'2009': 124, '2010': 124}}},
                    'energy': {
                        'total': {
                            'baseline': {'2009': 2480, '2010': 2480},
                            'efficient': {'2009': 1488, '2010': 1488}},
                        'competed': {
                            'baseline': {'2009': 1240, '2010': 1240},
                            'efficient': {'2009': 248, '2010': 248}}},
                    'carbon': {
                        'total': {
                            'baseline': {'2009': 3720, '2010': 3720},
                            'efficient': {'2009': 2232, '2010': 2232}},
                        'competed': {
                            'baseline': {'2009': 1860, '2010': 1860},
                            'efficient': {'2009': 372, '2010': 372}}},
                    'cost': {
                        'stock': {
                            'total': {
                                'baseline': {'2009': 340, '2010': 340},
                                'efficient': {'2009': 612, '2010': 612}},
                            'competed': {
                                'baseline': {'2009': 340, '2010': 340},
                                'efficient': {'2009': 612, '2010': 612}}},
                        'energy': {
                            'total': {
                                'baseline': {'2009': 680, '2010': 680},
                                'efficient': {'2009': 408, '2010': 408}},
                            'competed': {
                                'baseline': {'2009': 340, '2010': 340},
                                'efficient': {'2009': 68, '2010': 68}}},
                        'carbon': {
                            'total': {
                                'baseline': {'2009': 1020, '2010': 1020},
                                'efficient': {'2009': 612, '2010': 612}},
                            'competed': {
                                'baseline': {'2009': 510, '2010': 510},
                                'efficient': {'2009': 102, '2010': 102}}}},
                        "lifetime": {
                            "baseline": {'2010': (41 / 1240),
                                         '2009': (41 / 1240)},
                            "measure": 13.29}},
                "mseg_adjust": {
                    "contributing mseg keys and values": {
                        ("('primary', AIA_CZ1', 'single family home', "
                         "'natural gas', 'water heating', None, 'new')"): {
                            "stock": {
                                "total": {
                                    "all": {"2009": 10, "2010": 10},
                                    "measure": {"2009": 6, "2010": 6}},
                                "competed": {
                                    "all": {"2009": 5, "2010": 5},
                                    "measure": {"2009": 1, "2010": 1}}},
                            "energy": {
                                "total": {
                                    "baseline": {"2009": 20, "2010": 20},
                                    "efficient": {"2009": 12, "2010": 12}},
                                "competed": {
                                    "baseline": {"2009": 10, "2010": 10},
                                    "efficient": {"2009": 2, "2010": 2}}},
                            "carbon": {
                                "total": {
                                    "baseline": {"2009": 30, "2010": 30},
                                    "efficient": {"2009": 18, "2010": 18}},
                                "competed": {
                                    "baseline": {"2009": 15, "2010": 15},
                                    "efficient": {"2009": 3, "2010": 3}}},
                            "cost": {
                                "stock": {
                                    "total": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {
                                            "2009": 18, "2010": 18}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 20, "2010": 20},
                                        "efficient": {"2009": 12, "2010": 12}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 2, "2010": 2}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 30, "2010": 30},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 15, "2010": 15},
                                        "efficient": {"2009": 3, "2010": 3}}}},
                            "lifetime": {
                                "baseline": {"2009": 5, "2010": 5},
                                "measure": 10},
                            "sub-market scaling": 1},
                        ("('primary', AIA_CZ1', 'single family home', "
                         "'natural gas', 'water heating', None, "
                         "'existing')"): {
                            "stock": {
                                "total": {
                                    "all": {"2009": 10, "2010": 10},
                                    "measure": {"2009": 6, "2010": 6}},
                                "competed": {
                                    "all": {"2009": 5, "2010": 5},
                                    "measure": {"2009": 1, "2010": 1}}},
                            "energy": {
                                "total": {
                                    "baseline": {"2009": 20, "2010": 20},
                                    "efficient": {"2009": 12, "2010": 12}},
                                "competed": {
                                    "baseline": {"2009": 10, "2010": 10},
                                    "efficient": {"2009": 2, "2010": 2}}},
                            "carbon": {
                                "total": {
                                    "baseline": {"2009": 30, "2010": 30},
                                    "efficient": {"2009": 18, "2010": 18}},
                                "competed": {
                                    "baseline": {"2009": 15, "2010": 15},
                                    "efficient": {"2009": 3, "2010": 3}}},
                            "cost": {
                                "stock": {
                                    "total": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {
                                            "2009": 18, "2010": 18}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 20, "2010": 20},
                                        "efficient": {"2009": 12, "2010": 12}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 2, "2010": 2}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 30, "2010": 30},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 15, "2010": 15},
                                        "efficient": {"2009": 3, "2010": 3}}}},
                            "lifetime": {
                                "baseline": {"2009": 5, "2010": 5},
                                "measure": 10},
                            "sub-market scaling": 1},
                        ("('primary', AIA_CZ2', 'single family home', "
                         "'natural gas', 'water heating', None, 'new')"): {
                            "stock": {
                                "total": {
                                    "all": {"2009": 10, "2010": 10},
                                    "measure": {"2009": 6, "2010": 6}},
                                "competed": {
                                    "all": {"2009": 5, "2010": 5},
                                    "measure": {"2009": 1, "2010": 1}}},
                            "energy": {
                                "total": {
                                    "baseline": {"2009": 20, "2010": 20},
                                    "efficient": {"2009": 12, "2010": 12}},
                                "competed": {
                                    "baseline": {"2009": 10, "2010": 10},
                                    "efficient": {"2009": 2, "2010": 2}}},
                            "carbon": {
                                "total": {
                                    "baseline": {"2009": 30, "2010": 30},
                                    "efficient": {"2009": 18, "2010": 18}},
                                "competed": {
                                    "baseline": {"2009": 15, "2010": 15},
                                    "efficient": {"2009": 3, "2010": 3}}},
                            "cost": {
                                "stock": {
                                    "total": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {
                                            "2009": 18, "2010": 18}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 20, "2010": 20},
                                        "efficient": {"2009": 12, "2010": 12}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 2, "2010": 2}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 30, "2010": 30},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 15, "2010": 15},
                                        "efficient": {"2009": 3, "2010": 3}}}},
                            "lifetime": {
                                "baseline": {"2009": 5, "2010": 5},
                                "measure": 10},
                            "sub-market scaling": 1},
                        ("('primary', AIA_CZ2', 'single family home', "
                         "'natural gas', 'water heating', None, "
                         "'existing')"): {
                            "stock": {
                                "total": {
                                    "all": {"2009": 10, "2010": 10},
                                    "measure": {"2009": 6, "2010": 6}},
                                "competed": {
                                    "all": {"2009": 5, "2010": 5},
                                    "measure": {"2009": 1, "2010": 1}}},
                            "energy": {
                                "total": {
                                    "baseline": {"2009": 20, "2010": 20},
                                    "efficient": {"2009": 12, "2010": 12}},
                                "competed": {
                                    "baseline": {"2009": 10, "2010": 10},
                                    "efficient": {"2009": 2, "2010": 2}}},
                            "carbon": {
                                "total": {
                                    "baseline": {"2009": 30, "2010": 30},
                                    "efficient": {"2009": 18, "2010": 18}},
                                "competed": {
                                    "baseline": {"2009": 15, "2010": 15},
                                    "efficient": {"2009": 3, "2010": 3}}},
                            "cost": {
                                "stock": {
                                    "total": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {
                                            "2009": 18, "2010": 18}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 20, "2010": 20},
                                        "efficient": {"2009": 12, "2010": 12}},
                                    "competed": {
                                        "baseline": {"2009": 10, "2010": 10},
                                        "efficient": {"2009": 2, "2010": 2}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 30, "2010": 30},
                                        "efficient": {"2009": 18, "2010": 18}},
                                    "competed": {
                                        "baseline": {"2009": 15, "2010": 15},
                                        "efficient": {"2009": 3, "2010": 3}}}},
                            "lifetime": {
                                "baseline": {"2009": 5, "2010": 5},
                                "measure": 10},
                            "sub-market scaling": 1},
                        ("('primary', AIA_CZ1', 'single family home', "
                             "'electricity',"
                             "'lighting', 'reflector (incandescent)', "
                             "'existing')"): {
                                "stock": {
                                    "total": {
                                        "all": {"2009": 100, "2010": 100},
                                        "measure": {"2009": 60, "2010": 60}},
                                    "competed": {
                                        "all": {"2009": 50, "2010": 50},
                                        "measure": {"2009": 10, "2010": 10}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 200, "2010": 200},
                                        "efficient": {
                                            "2009": 120, "2010": 120}},
                                    "competed": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 20, "2010": 20}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 300, "2010": 300},
                                        "efficient": {
                                            "2009": 180, "2010": 180}},
                                    "competed": {
                                        "baseline": {"2009": 150, "2010": 150},
                                        "efficient": {
                                            "2009": 30, "2010": 30}}},
                                "cost": {
                                    "stock": {
                                        "total": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 180, "2010": 180}}},
                                    "energy": {
                                        "total": {
                                            "baseline": {
                                                "2009": 200, "2010": 200},
                                            "efficient": {
                                                "2009": 120, "2010": 120}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 100, "2010": 100},
                                            "efficient": {
                                                "2009": 20, "2010": 20}}},
                                    "carbon": {
                                        "total": {
                                            "baseline": {
                                                "2009": 300, "2010": 300},
                                            "efficient": {
                                                "2009": 180, "2010": 180}},
                                        "competed": {
                                            "baseline": {
                                                "2009": 150, "2010": 150},
                                            "efficient": {
                                                "2009": 30, "2010": 30}}}},
                                "lifetime": {
                                    "baseline": {"2009": 1, "2010": 1},
                                    "measure": 20},
                                "sub-market scaling": 1},
                        ("('primary', AIA_CZ1', 'single family home', "
                         "'electricity',"
                         "'lighting', 'reflector (halogen)', 'existing')"): {
                            "stock": {
                                "total": {
                                    "all": {"2009": 100, "2010": 100},
                                    "measure": {"2009": 60, "2010": 60}},
                                "competed": {
                                    "all": {"2009": 50, "2010": 50},
                                    "measure": {"2009": 10, "2010": 10}}},
                            "energy": {
                                "total": {
                                    "baseline": {"2009": 200, "2010": 200},
                                    "efficient": {"2009": 120, "2010": 120}},
                                "competed": {
                                    "baseline": {"2009": 100, "2010": 100},
                                    "efficient": {"2009": 20, "2010": 20}}},
                            "carbon": {
                                "total": {
                                    "baseline": {"2009": 300, "2010": 300},
                                    "efficient": {"2009": 180, "2010": 180}},
                                "competed": {
                                    "baseline": {"2009": 150, "2010": 150},
                                    "efficient": {"2009": 30, "2010": 30}}},
                            "cost": {
                                "stock": {
                                    "total": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 180, "2010": 180}},
                                    "competed": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 180, "2010": 180}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 200, "2010": 200},
                                        "efficient": {
                                            "2009": 120, "2010": 120}},
                                    "competed": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 20, "2010": 20}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 300, "2010": 300},
                                        "efficient": {
                                            "2009": 180, "2010": 180}},
                                    "competed": {
                                        "baseline": {"2009": 150, "2010": 150},
                                        "efficient": {
                                            "2009": 30, "2010": 30}}}},
                            "lifetime": {
                                "baseline": {"2009": 2, "2010": 2},
                                "measure": 15},
                            "sub-market scaling": 1},
                        ("('primary', AIA_CZ5', 'single family home', "
                         "'electricity',"
                         "'cooling', 'supply', 'ASHP', 'new')"): {
                            "stock": {
                                "total": {
                                    "all": {"2009": 1000, "2010": 1000},
                                    "measure": {"2009": 600, "2010": 600}},
                                "competed": {
                                    "all": {"2009": 500, "2010": 500},
                                    "measure": {"2009": 100, "2010": 100}}},
                            "energy": {
                                "total": {
                                    "baseline": {"2009": 2000, "2010": 2000},
                                    "efficient": {"2009": 1200, "2010": 1200}},
                                "competed": {
                                    "baseline": {"2009": 1000, "2010": 1000},
                                    "efficient": {"2009": 200, "2010": 200}}},
                            "carbon": {
                                "total": {
                                    "baseline": {"2009": 3000, "2010": 3000},
                                    "efficient": {"2009": 1800, "2010": 1800}},
                                "competed": {
                                    "baseline": {"2009": 1500, "2010": 1500},
                                    "efficient": {"2009": 300, "2010": 300}}},
                            "cost": {
                                "stock": {
                                    "total": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 180, "2010": 180}},
                                    "competed": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 180, "2010": 180}}},
                                "energy": {
                                    "total": {
                                        "baseline": {"2009": 200, "2010": 200},
                                        "efficient": {
                                            "2009": 120, "2010": 120}},
                                    "competed": {
                                        "baseline": {"2009": 100, "2010": 100},
                                        "efficient": {
                                            "2009": 20, "2010": 20}}},
                                "carbon": {
                                    "total": {
                                        "baseline": {"2009": 300, "2010": 300},
                                        "efficient": {
                                            "2009": 180, "2010": 180}},
                                    "competed": {
                                        "baseline": {"2009": 150, "2010": 150},
                                        "efficient": {
                                            "2009": 30, "2010": 30}}}},
                            "lifetime": {
                                "baseline": {"2009": 18, "2010": 18},
                                "measure": 18},
                            "sub-market scaling": 1}},
                    "competed choice parameters": {
                        ("('primary', AIA_CZ1', 'single family home', "
                         "'natural gas', 'water heating', None, 'new')"): {
                            "b1": {"2009": 0.5, "2010": 0.5},
                            "b2": {"2009": 0.5, "2010": 0.5}},
                        ("('primary', AIA_CZ1', 'single family home', "
                         "'natural gas', 'water heating', None, "
                         "'existing')"): {
                            "b1": {"2009": 0.5, "2010": 0.5},
                            "b2": {"2009": 0.5, "2010": 0.5}},
                        ("('primary', AIA_CZ2', 'single family home', "
                         "'natural gas', 'water heating', None, 'new')"): {
                            "b1": {"2009": 0.5, "2010": 0.5},
                            "b2": {"2009": 0.5, "2010": 0.5}},
                        ("('primary', AIA_CZ2', 'single family home', "
                         "'natural gas', 'water heating', None, "
                         "'existing')"): {
                            "b1": {"2009": 0.5, "2010": 0.5},
                            "b2": {"2009": 0.5, "2010": 0.5}},
                        ("('primary', AIA_CZ1', 'single family home', "
                         "'electricity',"
                         "'lighting', 'reflector (incandescent)', "
                         "'existing')"): {
                            "b1": {"2009": 0.25, "2010": 0.25},
                            "b2": {"2009": 0.25, "2010": 0.25}},
                        ("('primary', AIA_CZ1', 'single family home', "
                         "'electricity',"
                         "'lighting', 'reflector (halogen)', "
                         "'existing')"): {
                            "b1": {"2009": 0.25, "2010": 0.25},
                            "b2": {"2009": 0.25, "2010": 0.25}},
                        ("('primary', AIA_CZ5', 'single family home', "
                         "'electricity',"
                         "'cooling', 'supply', 'ASHP', 'new')"): {
                            "b1": {"2009": 0.75, "2010": 0.75},
                            "b2": {"2009": 0.75, "2010": 0.75}}},
                    "secondary mseg adjustments": {
                        "sub-market": {
                            "original energy (total)": {},
                            "adjusted energy (sub-market)": {}},
                        "stock-and-flow": {
                            "original energy (total)": {},
                            "adjusted energy (previously captured)": {},
                            "adjusted energy (competed)": {},
                            "adjusted energy (competed and captured)": {}},
                        "market share": {
                            "original energy (total captured)": {},
                            "original energy (competed and captured)": {},
                            "adjusted energy (total captured)": {},
                            "adjusted energy (competed and captured)": {}}}},
                "mseg_out_break": {
                    'AIA CZ1': {
                        'Residential (New)': {
                            'Cooling (Equip.)': {},
                            'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {"2009": 0.016, "2010": 0.016},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Residential (Existing)': {
                            'Cooling (Equip.)': {},
                            'Ventilation': {},
                            'Lighting': {
                                "2009": 0.5510753,
                                "2010": 0.5510753},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {"2009": 0, "2010": 0},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (New)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (Existing)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}}},
                    'AIA CZ2': {
                        'Residential (New)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {"2009": 0.016, "2010": 0.016},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Residential (Existing)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {"2009": 0, "2010": 0},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (New)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (Existing)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}}},
                    'AIA CZ3': {
                        'Residential (New)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Residential (Existing)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (New)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (Existing)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}}},
                    'AIA CZ4': {
                        'Residential (New)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Residential (Existing)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (New)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (Existing)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}}},
                    'AIA CZ5': {
                        'Residential (New)': {
                            'Cooling (Equip.)': {
                                "2009": 0.4166667, "2010": 0.4166667},
                            'Ventilation': {}, 'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Residential (Existing)': {
                            'Cooling (Equip.)': {},
                            'Ventilation': {}, 'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (New)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}},
                        'Commercial (Existing)': {
                            'Cooling (Equip.)': {}, 'Ventilation': {},
                            'Lighting': {},
                            'Refrigeration': {}, 'Other': {},
                            'Water Heating': {},
                            'Computers and Electronics': {},
                            'Heating (Equip.)': {}, 'Envelope': {}}}}}}
        cls.mseg_ok_in_test2 = {
            "stock": {
                "total": {
                    "all": {"2009": 40, "2010": 40},
                    "measure": {"2009": 24, "2010": 24}},
                "competed": {
                    "all": {"2009": 20, "2010": 20},
                    "measure": {"2009": 4, "2010": 4}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 80, "2010": 80},
                    "efficient": {"2009": 48, "2010": 48}},
                "competed": {
                    "baseline": {"2009": 40, "2010": 40},
                    "efficient": {"2009": 8, "2010": 8}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 120, "2010": 120},
                    "efficient": {"2009": 72, "2010": 72}},
                "competed": {
                    "baseline": {"2009": 60, "2010": 60},
                    "efficient": {"2009": 12, "2010": 12}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 40, "2010": 40},
                        "efficient": {"2009": 72, "2010": 72}},
                    "competed": {
                        "baseline": {"2009": 40, "2010": 40},
                        "efficient": {"2009": 72, "2010": 72}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 80, "2010": 80},
                        "efficient": {"2009": 48, "2010": 48}},
                    "competed": {
                        "baseline": {"2009": 40, "2010": 40},
                        "efficient": {"2009": 8, "2010": 8}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 120, "2010": 120},
                        "efficient": {"2009": 72, "2010": 72}},
                    "competed": {
                        "baseline": {"2009": 60, "2010": 60},
                        "efficient": {"2009": 12, "2010": 12}}}},
            "lifetime": {
                "baseline": {"2009": 5, "2010": 5},
                "measure": 10}}
        cls.mseg_ok_out_test2 = {
            "stock": {
                "total": {
                    "all": {"2009": 40, "2010": 40},
                    "measure": {"2009": 24, "2010": 24}},
                "competed": {
                    "all": {"2009": 20, "2010": 20},
                    "measure": {"2009": 4, "2010": 4}}},
            "energy": {
                "total": {
                    "baseline": {"2009": 80, "2010": 80},
                    "efficient": {"2009": 38.4, "2010": 38.4}},
                "competed": {
                    "baseline": {"2009": 40, "2010": 40},
                    "efficient": {"2009": 0, "2010": 0}}},
            "carbon": {
                "total": {
                    "baseline": {"2009": 120, "2010": 120},
                    "efficient": {"2009": 57.6, "2010": 57.6}},
                "competed": {
                    "baseline": {"2009": 60, "2010": 60},
                    "efficient": {"2009": 0, "2010": 0}}},
            "cost": {
                "stock": {
                    "total": {
                        "baseline": {"2009": 40, "2010": 40},
                        "efficient": {"2009": 57.6, "2010": 57.6}},
                    "competed": {
                        "baseline": {"2009": 40, "2010": 40},
                        "efficient": {"2009": 57.6, "2010": 57.6}}},
                "energy": {
                    "total": {
                        "baseline": {"2009": 80, "2010": 80},
                        "efficient": {"2009": 38.4, "2010": 38.4}},
                    "competed": {
                        "baseline": {"2009": 40, "2010": 40},
                        "efficient": {"2009": 0, "2010": 0}}},
                "carbon": {
                    "total": {
                        "baseline": {"2009": 120, "2010": 120},
                        "efficient": {"2009": 57.6, "2010": 57.6}},
                    "competed": {
                        "baseline": {"2009": 60, "2010": 60},
                        "efficient": {"2009": 0, "2010": 0}}}},
            "lifetime": {
                "baseline": {"2009": 5, "2010": 5},
                "measure": 10}}

    def test_merge_measure(self):
        """Test 'merge_measures' function given valid inputs."""
        self.sample_package_in_test1.merge_measures()
        # Check for correct general attributes for packaged measure
        output_lists = [
            self.sample_package_in_test1.name,
            self.sample_package_in_test1.climate_zone,
            self.sample_package_in_test1.bldg_type,
            self.sample_package_in_test1.structure_type,
            self.sample_package_in_test1.fuel_type,
            self.sample_package_in_test1.end_use["primary"]]
        for ind in range(0, len(output_lists)):
            self.assertEqual(sorted(self.genattr_ok_out_test1[ind]),
                             sorted(output_lists[ind]))
        # Check for correct markets for packaged measure
        self.dict_check(
            self.sample_package_in_test1.markets, self.markets_ok_out_test1)

    def test_apply_pkg_benefits(self):
        """Test 'apply_pkg_benefits' function given valid inputs."""
        self.dict_check(
            self.sample_package_in_test2.apply_pkg_benefits(
                self.mseg_ok_in_test2),
            self.mseg_ok_out_test2)


class CleanUpTest(unittest.TestCase, CommonMethods):
    """Test 'split_clean_data' function.

    Ensure building vintage square footages are read in properly from a
    cbecs data file and that the proper weights are derived for mapping
    EnergyPlus building vintages to Scout's 'new' and 'retrofit' building
    structure types.

    Attributes:
        handyvars (object): Global variables to use for the test measure.
        sample_measlist_in (list): List of individual and packaged measure
            objects to clean up.
        sample_measlist_out_comp_data (list): Measure competition data that
            should be yielded by function given sample measures as input.
        sample_measlist_out_mkt_keys (list): High level measure summary data
            keys that should be yielded by function given sample measures as
            input.
        sample_measlist_out_highlev_keys (list): Measure 'markets' keys that
            should be yielded by function given sample measures as input.
        sample_pkg_meas_names (list): Updated 'contributing_ECMs'
            attribute that should be yielded by function for sample
            packaged measure.
    """

    @classmethod
    def setUpClass(cls):
        """Define variables and objects for use across all class functions."""
        # Base directory
        base_dir = os.getcwd()
        benefits = {
            "energy savings increase": None,
            "cost reduction": None}
        cls.handyvars = ecm_prep.UsefulVars(base_dir,
                                            ecm_prep.UsefulInputFiles())
        sample_measindiv_dicts = [{
            "name": "cleanup 1",
            "market_entry_year": None,
            "market_exit_year": None,
            "measure_type": "full service",
            "technology": {
                "primary": None, "secondary": None}},
            {
            "name": "cleanup 2",
            "market_entry_year": None,
            "market_exit_year": None,
            "measure_type": "full service",
            "technology": {
                "primary": None, "secondary": None}}]
        cls.sample_measlist_in = [ecm_prep.Measure(
            cls.handyvars, **x) for x in sample_measindiv_dicts]
        sample_measpackage = ecm_prep.MeasurePackage(
            copy.deepcopy(cls.sample_measlist_in), "cleanup 3",
            benefits, cls.handyvars)
        cls.sample_measlist_in.append(sample_measpackage)
        cls.sample_measlist_out_comp_data = [{
            "Technical potential": {
                "contributing mseg keys and values": {},
                "competed choice parameters": {},
                "secondary mseg adjustments": {
                    "market share": {
                        "original energy (total captured)": {},
                        "original energy (competed and captured)": {},
                        "adjusted energy (total captured)": {},
                        "adjusted energy (competed and captured)": {}}}},
            "Max adoption potential": {
                "contributing mseg keys and values": {},
                "competed choice parameters": {},
                "secondary mseg adjustments": {
                    "market share": {
                        "original energy (total captured)": {},
                        "original energy (competed and captured)": {},
                        "adjusted energy (total captured)": {},
                        "adjusted energy (competed and captured)": {}}}}},
            {
            "Technical potential": {
                "contributing mseg keys and values": {},
                "competed choice parameters": {},
                "secondary mseg adjustments": {
                    "market share": {
                        "original energy (total captured)": {},
                        "original energy (competed and captured)": {},
                        "adjusted energy (total captured)": {},
                        "adjusted energy (competed and captured)": {}}}},
            "Max adoption potential": {
                "contributing mseg keys and values": {},
                "competed choice parameters": {},
                "secondary mseg adjustments": {
                    "market share": {
                        "original energy (total captured)": {},
                        "original energy (competed and captured)": {},
                        "adjusted energy (total captured)": {},
                        "adjusted energy (competed and captured)": {}}}}},
            {
            "Technical potential": {
                "contributing mseg keys and values": {},
                "competed choice parameters": {},
                "secondary mseg adjustments": {
                    "market share": {
                        "original energy (total captured)": {},
                        "original energy (competed and captured)": {},
                        "adjusted energy (total captured)": {},
                        "adjusted energy (competed and captured)": {}}}},
            "Max adoption potential": {
                "contributing mseg keys and values": {},
                "competed choice parameters": {},
                "secondary mseg adjustments": {
                    "market share": {
                        "original energy (total captured)": {},
                        "original energy (competed and captured)": {},
                        "adjusted energy (total captured)": {},
                        "adjusted energy (competed and captured)": {}}}}}]
        cls.sample_measlist_out_mkt_keys = ["master_mseg", "mseg_out_break"]
        cls.sample_measlist_out_highlev_keys = [
            ["market_entry_year", "market_exit_year", "markets",
             "name", "out_break_norm", "remove", 'technology',
             'technology_type', 'time_sensitive_valuation',
             'yrs_on_mkt', 'measure_type'],
            ["market_entry_year", "market_exit_year", "markets",
             "name", "out_break_norm", "remove", 'technology',
             'technology_type', 'time_sensitive_valuation',
             'yrs_on_mkt', 'measure_type'],
            ['benefits', 'bldg_type', 'climate_zone', 'end_use', 'fuel_type',
             "technology", "technology_type",
             "market_entry_year", "market_exit_year", 'markets',
             'contributing_ECMs', 'name', "out_break_norm", 'remove',
             'structure_type', 'yrs_on_mkt', 'measure_type']]
        cls.sample_pkg_meas_names = [x["name"] for x in sample_measindiv_dicts]

    def test_cleanup(self):
        """Test 'split_clean_data' function given valid inputs."""
        # Execute the function
        measures_comp_data, measures_summary_data = \
            ecm_prep.split_clean_data(self.sample_measlist_in)
        # Check function outputs
        for ind in range(0, len(self.sample_measlist_in)):
            # Check measure competition data
            self.dict_check(self.sample_measlist_out_comp_data[ind],
                            measures_comp_data[ind])
            # Check measure summary data
            for adopt_scheme in self.handyvars.adopt_schemes:
                self.assertEqual(sorted(list(measures_summary_data[
                    ind].keys())),
                    sorted(self.sample_measlist_out_highlev_keys[ind]))
                self.assertEqual(sorted(list(measures_summary_data[
                    ind]["markets"][adopt_scheme].keys())),
                    sorted(self.sample_measlist_out_mkt_keys))
                # Verify correct updating of 'contributing_ECMs'
                # MeasurePackage attribute
                if "Package: " in measures_summary_data[ind]["name"]:
                    self.assertEqual(measures_summary_data[ind][
                        "contributing_ECMs"], self.sample_pkg_meas_names)


# Offer external code execution (include all lines below this point in all
# test files)
def main():
    """Trigger default behavior of running all test fixtures in the file."""
    unittest.main()


if __name__ == "__main__":
    main()
