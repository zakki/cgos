#!/bin/bash
TOPDIR=$(git rev-parse --show-toplevel)
GODIR="$TOPDIR/wgo_view"

# check if google closure compiler is installed
if [ ! -e "$GODIR/compiler/compiler.jar" ]; then
	echo "Google closure compiler not found. Downloading it from "
	echo
	echo "    https://github.com/google/closure-compiler"
	echo
	echo "and extracting it to the bin/compiler folder."
	echo

	mkdir -p $GODIR/compiler
	(
		cd $TOPDIR/wgo_view/compiler
		wget https://repo1.maven.org/maven2/com/google/javascript/closure-compiler/v20221102/closure-compiler-v20221102.jar -O compiler.jar
	)
fi

(
echo '-----------------------------'
echo ' Compressing JavaScript files'
echo '-----------------------------'
cd $GODIR/wgo
pwd

# compress wgo.js
java -jar $GODIR/compiler/compiler.jar \
	--language_in ECMASCRIPT5 \
	--js_output_file=_tmp.js wgo.js

# prepend licence information
echo -n '/*! MIT license, more info: wgo.waltheri.net */' > wgo.min.js
cat _tmp.js >> wgo.min.js
rm _tmp.js

# compress player
java -jar $GODIR/compiler/compiler.jar \
	--language_in ECMASCRIPT5 \
	--js_output_file=_tmp.js \
		kifu.js \
		sgfparser.js \
		player.js \
		basicplayer.js \
		basicplayer.component.js \
		basicplayer.infobox.js \
		basicplayer.commentbox.js \
		basicplayer.control.js \
		player.editable.js \
		player.cgos.js \
		scoremode.js \
		player.permalink.js

# prepend licence information
echo -n '/*! MIT license, more info: wgo.waltheri.net */' > wgo.player.min.js
cat _tmp.js >> wgo.player.min.js
rm _tmp.js
)