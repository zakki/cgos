"""
Copyright (C) 2009 Christian Nentwich and contributors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import sys, traceback
import os.path


class ConfigSection(object):
    """
    A config section has a name (e.g. "Engine") and a list of values, which are
    name/value tuples, e.g. [("host", "cgos.boardspace.net"), ("port", "1919")]
    """

    def __init__(self, name):
        self._name = name
        self._values = {}

    def addValue(self, name, value):
        self._values[name] = value

    def getValue(self, name):
        return self._values[name]

    def hasValue(self, name):
        return name in self._values

    def name(self):
        return self._name

    def values(self):
        return self._values


class ConfigFile(object):
    """
    Configuration file loader. Loads the file as a list of ConfigSection objects.
    Also has a few utility methods for obtaining required standard sections like the
    server.
    """

    ENGINE_SECTION = "GTPEngine"

    COMMON_SECTION = "Common"

    OBSERVER_SECTION = "GTPObserver"

    COMMAND_LINE = "CommandLine"

    def __init__(self):
        self._sections = []

    def load(self, fileName):
        """
        Load from fileName and populate sections list
        """
        self._sections = []

        file = open(fileName, "r")
        lines = file.readlines()
        file.close()

        currentSection = None

        for line in lines:
            line = line.strip()

            if len(line) == 0 or line[0] == "#":
                continue

            if line[-1] == ":":
                currentSection = ConfigSection(line[0 : len(line) - 1])
                self._sections.append(currentSection)
            elif "=" in line and currentSection is not None:
                param = line.split("=", 1)
                currentSection.addValue(param[0].strip(), param[1].strip())

        self._validate()

    def getCommonSection(self):
        return [x for x in self._sections if x.name() == ConfigFile.COMMON_SECTION][0]

    def getEngineSections(self):
        return [x for x in self._sections if x.name() == ConfigFile.ENGINE_SECTION]

    def getObserverSection(self):
        result = [x for x in self._sections if x.name() == ConfigFile.OBSERVER_SECTION]
        if len(result) > 0:
            return result[0]

    def sections(self):
        return self._sections

    def _validate(self):
        hasEngine = False
        hasCommon = False

        for section in self._sections:
            if section.name() == ConfigFile.ENGINE_SECTION:
                hasEngine = True

                for req in [
                    "Name",
                    "CommandLine",
                    "ServerHost",
                    "ServerPort",
                    "ServerUser",
                    "ServerPassword",
                    "NumberOfGames",
                ]:
                    if not (section.hasValue(req)):
                        raise Exception("Mandatory engine attribute missing: " + req)

                try:
                    if int(section.getValue("NumberOfGames")) <= 0:
                        raise Exception(
                            "Configuration attribute 'NumberOfGames' must be greater than zero"
                        )
                except ValueError:
                    raise Exception(
                        "Configuration attribute 'NumberOfGames' must be an integer"
                    )

                if section.hasValue("SGFDirectory"):
                    dir = section.getValue("SGFDirectory")
                    if not (os.path.exists(dir)) or not (os.path.isdir(dir)):
                        raise Exception("SGF directory " + dir + " does not exist")

            if section.name() == ConfigFile.COMMON_SECTION:
                hasCommon = True
                for req in ["KillFile"]:
                    if not (section.hasValue(req)):
                        raise Exception(
                            "Mandatory common section attribute missing: " + req
                        )

        if not (hasEngine) or not (hasCommon):
            raise Exception(
                "At least one engine must be defined in the configuration, as well as a common section"
            )


def main():
    config = ConfigFile()
    config.load("../testdata/local.cfg")

    for section in config.sections():
        print("Section: " + section.name())
        for x in list(section.values()):
            print("   " + x + " = " + list(section.values())[x])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
