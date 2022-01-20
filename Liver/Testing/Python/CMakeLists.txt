
# Test markups pluggable architecture
slicerMacroBuildScriptedModule(
  NAME DistanceMapsSelfTest
  SCRIPTS DistanceMapsSelfTest.py
  RESOURCES ${MARKUPS_PYTHON_RESOURCES}
  )
slicer_add_python_unittest(SCRIPT DistanceMapsSelfTest.py)
