#!/usr/bin/perl
#http://sgfview.cgi?tanaka=11&takeuti=550
#GET is QUERY_STRING
$formin = $ENV{'QUERY_STRING'};

@indata = split (/&/,$formin); #

foreach $tmp (@indata) #
{
#	($name,$value) = split (/=/,$tmp); #
#	print "$name $value<BR>\n";
}

$length = @indata;
$moves = "";
if ( $length == 2 ) {
    $moves = "data-wgo-move=\"${indata[1]}\"";
}

print "Content-type: text/html\n\n";
print <<"HTML";
<!DOCTYPE HTML>
<html>
<head>
<title>sgf viewer</title>
<script type="text/javascript" src="wgo/wgo.min.js"></script>
<script type="text/javascript" src="wgo/wgo.player.min.js"></script>
<link type="text/css" href="wgo/wgo.player.css" rel="stylesheet" />
</head>
<body>
<div data-wgo="${indata[0]}" style="width: 95vw" ${moves}>
Sorry, your browser doesn't support WGo.js. Download SGF <a href="${formin}">directly</a>.
</div>
</body></html>
HTML

exit;
