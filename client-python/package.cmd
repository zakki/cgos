@echo off
md release
md release\bin
copy src\*.py release\bin
md release\doc
copy doc\*.html release\doc
copy readme.txt release
copy sample.cfg release