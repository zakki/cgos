# The MIT License
#
# Copyright (c) <year> <copyright holders>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
package provide app-webuild 1.0
package require sqlite3



proc log {msg} {
    set tme [clock format [clock seconds] -format "%Y-%m-%d %H:%M:%S" -timezone :UTC]
    puts  "$tme | $msg" 
}


proc gidcmp {a b} {
    set a1 [lindex $a 0]
    set b1 [lindex $b 0]

    if {$a1 < $b1} {
	return 1
    } elseif {$a1 > $b1} {
	return -1
    } else {
	return 0
    }
}

array set rating {}


proc crosstable {who} {
    
    global  htmlDir
    global  rating

    puts "building for $who"


    db transaction {
	set wgms [cgi eval {SELECT gid, b, br, res FROM games WHERE w=$who ORDER BY gid} ]
	set bgms [cgi eval {SELECT gid, w, wr, res FROM games WHERE b=$who ORDER BY gid} ]
    }

    foreach {gid opp r res} $wgms {
	if { [catch { incr count($opp) }] } {
	    set count($opp) 1
	    set wins($opp) 0
	}

	if { [string index $res 0] == "W" } {set w 1} else {set w 0}
	incr wins($opp) $w
	set arate($opp) [list $gid $r]
	set brate($opp) [list $gid $r]
    }

    foreach {gid opp r res} $bgms {
	if { [catch { incr count($opp) }] } {
	    set count($opp) 1
	    set wins($opp) 0
	}
	if { [string index $res 0] == "B" } {set w 1} else {set w 0}
	incr wins($opp) $w
	set brate($opp) [list $gid $r]
	if {![info exists arate($opp)]} {
	    set arate($opp) [list $gid $r]
	}
    }

    set olst [array names count]

    set  lst {}

    foreach n $olst {
	set ga [lindex $arate($n) 0]
	set gb [lindex $brate($n) 0]
	
	if {$ga > $gb} { 
	    set r [lindex $arate($n) 1] 
	} else {
	    set r [lindex $brate($n) 1]
	}

	set winp [format "%0.2f" [expr 100.0 * ($wins($n) / ($count($n) + 0.0))]]

	regexp {(\d+)} $r dmy rr

	lappend lst [format "%6d %s %7.2f %d %d" $rr $n $winp $wins($n) $count($n)]
    }

    set lst [lsort $lst]

    set  now [clock seconds]
    set  dte [clock format $now -format "%Y-%m-%d %T" -gmt 1]
	
    # put the css here
    # --------------------------------------
    set rpt {}
    append rpt "<html>\n"
    append rpt "<title>Crosstable for $who</title>\n"
    append rpt "<head>\n"
    append rpt "<style type=\"text/css\">\n"
    append rpt "table.solid \{border-style:solid ; border-width: 1px 1px 1px 1px \}\n"
    append rpt "tr.solid \{border-style:solid ; border-width: 1px 1px 1px 1px \}\n"
    append rpt ".centeredImage {text-align:center; margin-top:0px; margin-botom:0px; padding:0px;}"
    append rpt "</style>\n"
    append rpt "</head>\n"

    append rpt {<body BGCOLOR="#ECECEA" TEXT="#001000" LINK="#406040" ALINK="#80B080" VLINK="#406040"><p>}
    append rpt "\n"
    append rpt {<p class="centeredImage"><img src="../images/cgosLogo.jpg"></p>}

    # append rpt "<FONT COLOR=\"\#004000\"></FONT>\n"

    if { [info exists rating($who)] } {
	set rat $rating($who)
    } else {
	set rat "??"
    }
    
    append rpt "<H3 ALIGN=CENTER>Cross-table of results for $who</H3>\n"
    append rpt "<H3 ALIGN=CENTER>Rated: $rat</H3>\n"
    append rpt "<H4 ALIGN=CENTER>as of $dte</H4>\n"
    append rpt "<p>&nbsp;<p>\n"
    
    append rpt "<center><table class=solid cellspacing=0 justify=center>\n"
    append rpt "<colgroup span=4><col width=210></col><col width=100></col><col width=100></col><col width=100></col></colgroup>\n"
    
    append rpt "<tr BGCOLOR=\"\#708070\" style=\"color:white\">\n"
    append rpt "<th align=left>Opponent</th>"
    append rpt "<th align=left>Rating</th>"
    append rpt "<th align=left>Result</th>"
    append rpt "<th align=left>Percent</th>"
    append rpt "</tr>\n"
    append rpt "</table>\n"
    
    append rpt "<p style=\"margin: 3px\">\n"
    
    set tog [list "\#e0e0e0" "\#ffffff" ]
    set tcc 0
    
    append rpt "<center><table class=solid cellspacing=0 justify=center style=\"font-family;verdana;font-size:80%\">\n"
    append rpt "<colgroup span=4><col width=210></col><col width=100><col width=100></col><col width=100></col></colgroup>\n"

    foreach rec $lst {
	lassign $rec rat opp winp twins tgames
	append rpt "<tr bgcolor=\"[lindex $tog $tcc]\">"
	append rpt "<td>$opp</td><td>$rat</td><td class=solid>$twins / $tgames</td><td class=solid>$winp</td></tr>\n"
	set tcc [expr $tcc ^ 1]
    }
	
    append rpt "</table></center>\n"
    append rpt "<p>&nbsp;<p>\n"
    append rpt "<H4 align=center>"
    append rpt "<a href=\"../standings.html\">Returns to Current Standings Page.</a>"
    append rpt "</H4><br>"
    append rpt "</body>\n"
    append rpt "</hmtl>\n"

    puts  "trying to open and write: $htmlDir/cross/$who.html"
    set f [open $htmlDir/cross/$who.html w]
    puts $f $rpt
    close $f
}




proc  buildWebPage {} {
    global  web_data_file
    global  tmpfile
    global  pageName
    global  htmlInfoMsg
    global  serverName
    global  level
    global  provisionalAge
    global  establishedAge
    global  sgfDir
    global  rating

    set right_now [clock format [clock seconds] -format "%Y-%m-%d %H:%M:%S UCT" -timezone :UTC]

    set f [open $web_data_file]
    set wf [open $tmpfile w]

    set tme [clock format [clock seconds] -format "%Y-%m-%d %H:%M" -timezone :UTC]

    set players {}
    set gms {}
    set sch {}
    array set active {}

    # read in the data
    # ----------------

    while { [gets $f s] >= 0 } {

	switch [string index $s 0] {

	    "u" {
		lassign $s dmy nme cnt rat dte tme lgm
		if { [regexp {(\d+)\?} $rat dmy r] } {
		    set usr($nme) [format "%6d 0 %s %s %s" $r $nme $cnt "$dte $tme"]
		    lappend players $usr($nme)
		} else {
		    set usr($nme) [format "%6d 1 %s %s %s" $rat $nme $cnt "$dte $tme"]
		    lappend players $usr($nme)
		}
	    }

	    "g" {
		lassign $s dmy gid w wr b br dte tme wtl btl res
		lappend gms [list $gid $w $wr $b $br "$dte $tme" $wtl $btl $res]
		set bcr($w) 1
		set bcr($b) 1
	    }
	    
	    "s" {
		lassign $s dmy dte tme gid w b x wtl btl wr br
		lappend sch [list $gid $w $wr $b $br "$dte $tme"]
		set active($w) $gid
		set active($b) $gid
	    }
	}
    }

    close $f

    puts $wf "<html>\n"
    puts $wf "<title>$serverName</title>"
    puts $wf "<head>"
    puts $wf {<style type="text/css">}
    puts $wf "table.solid {border-style:solid ; border-width: 1px 1px 1px 1px }"
    puts $wf "tr.solid {border-style:solid ; border-width: 1px 1px 1px 1px }"
    puts $wf ".centeredImage {text-align:center; margin-top:0px; margin-botom:0px; padding:0px;}"
    puts $wf {</style>}
    puts $wf "</head>"
    puts $wf "\n"

    puts $wf {<body BGCOLOR="#ECECEA" TEXT="#001000" LINK="#002000" ALINK="#507050" VLINK="#002000"><p>}
    puts $wf {<p class="centeredImage"><img src="images/cgosLogo.jpg"></p>}
    puts $wf "<FONT COLOR=\"002000\"><H3 ALIGN=CENTER>$htmlInfoMsg</H3></FONT>"
    puts $wf {<P>}
    puts $wf "<FONT COLOR=\"002000\"><H4 ALIGN=CENTER>Last Update: $right_now</H4></FONT>"
    puts $wf {<P>}
    puts $wf  {<H4><center><a href="http://senseis.xmp.net/?ComputerGoServer">Sensei's Computer Go Server Page</a></center></H4>}
    puts $wf {<p><p><p>}

    puts $wf {<center><table border=1 cellpadding=4 cellspacing=0 justify=center style="font-family;verdana;font-size:90%">}
    puts $wf {<tr BGCOLOR="#708070" style="color:white"><th>Game</th><th>Program Name</th><th>Rating</th><th>Games Played</th><th>Last Game</th></tr>}

    set  cur_time [clock seconds]
    set  pa [expr $provisionalAge * 86400]  ;# provisional age in seconds
    set  ea [expr $establishedAge * 86400]  ;# established age in seconds

    set  pcut [expr int($cur_time - $pa)]
    set  pcut [clock format $pcut -format "%Y-%m-%d %H:%M:%S" -timezone :UTC]

    set  ecut [expr int($cur_time - $ea)]
    set  ecut [clock format $ecut -format "%Y-%m-%d %H:%M:%S" -timezone :UTC]

    foreach rec [lsort -decreasing $players] {
	lassign $rec rat k nme cnt dte tme

	set dtime "$dte $tme"

	if {$k == 0} {
	    puts "$nme -> $dtime"
	    puts "$nme -> $pcut\n"

	    # provisionally rated player
	    if {$dtime < $pcut} {
		puts "$nme being excluded"
		continue
	    }
	}

	if {$k == 1} {
	    if {$dtime < $ecut} {
		continue
	    }
	}

	set bg "\#ffffff"
	if { $k == 0 } { 
	    set bg "\#ffff80" 
	    set rat "$rat?"
	} 

	if { [info exists active($nme)] } {
	    set status $active($nme)
	} else {
	    set status "&mdash;"
	}

	puts -nonewline $wf "<tr bgcolor=\"$bg\"><td align=center>$status</td>"
	puts $wf "<td><a href=\"cross/$nme.html\">$nme</a></td><td>$rat</td><td align=center>$cnt</td><td>$dte $tme</td></tr>"
    }

    puts $wf "</table></center>"
    puts $wf {<P>&nbsp;<P>&nbsp;<P>}


    # -------------------------------------------------------------------------------------------------------------------



    puts $wf "<H4 ALIGN=CENTER>Recent Games</H4>\n"

    puts $wf "<center><table class=solid cellspacing=0 justify=center style=\"font-family;verdana;font-size:90%\">"
    puts $wf "<colgroup span=5><col width=80></col><col width=200></col><col width=80></col>"
    puts $wf "<col width=200></col><col width=80></col><col width=110></col></colgroup>"
    
    puts $wf "<tr BGCOLOR=\"#708070\" style=\"color:white\">\n"
    puts $wf "<th align=center>Game</th>"
    puts $wf "<th align=left>White</th>"
    puts $wf "<th align=left>Time</th>"
    puts $wf "<th align=left>Black</th>"
    puts $wf "<th align=left>Time</th>"
    puts $wf "<th align=left>Result</th>"
    puts $wf "</tr>\n"
    puts $wf "</table></center>\n\n"

    puts $wf "<p style=\"margin: 3px\">\n"

    puts $wf "<center><table class=solid cellspacing=0 justify=center style=\"font-family;verdana;font-size:75%\">\n"
    puts $wf "<colgroup span=5><col width=80></col><col width=200></col><col width=80></col>"
    puts $wf "<col width=200></col><col width=80><col width=110></col></colgroup>\n"

    # set tog [list "\#f0f0d0" "\#c0d0c0" ]
    set tog [list "\#f0f0e0" "\#c8d0c8" ]
    set tcc 0

    # insert games being played in this round
    # ---------------------------------------
    # lappend sch [list $gid $w $wr $b $br "$dte $tme"]
    foreach rec $sch {
	lassign $rec gid w wr b br tme
	set  wn  "$w\($wr\)"
	set  bn  "$b\($br\)"

	set  re {- playing ...}
	set  tme "&mdash;"
	set  tw "&mdash;"
	set  tb "&mdash;"
	
	puts $wf "<tr bgcolor=\"[lindex $tog $tcc]\">"
	puts $wf "<td align=center>$gid</td><td>$wn</td><td>$tw</td><td>$bn</td><td>$tb</td><td>$re</td></tr>\n"

	set tcc [expr $tcc ^ 1]
    }



    # insert games from previous rounds here
    # ---------------------------------------
    # lappend gms [list $gid $w $wr $b $br "$dte $tme" $wtl $btl $res]

    foreach rec [lsort -command gidcmp $gms] {
	lassign $rec gid w wr b br tme wtl btl res
	set  wn  "$w\($wr\)"
	set  bn  "$b\($br\)"

	set  tw [expr $wtl / 1000]
	set  tb [expr $btl / 1000]
	
	set  tw [format "%02d:%02d" [expr $tw / 60] [expr $tw % 60]]
	set  tb [format "%02d:%02d" [expr $tb / 60] [expr $tb % 60]]
	
	puts $wf "<tr bgcolor=\"[lindex $tog $tcc]\">"

	set sgfpath "$sgfDir/"
	append sgfpath "[string range $tme 0 3]/"
	append sgfpath "[string range $tme 5 6]/"
	append sgfpath "[string range $tme 8 9]/$gid.sgf"

	if { [string index $res 0] == "W" } {
	    puts $wf "<td align=center><a href=\"$sgfpath\">$gid</a></td><td><b>$wn</b></td><td>$tw</td><td>$bn</td><td>$tb</td><td>$res</td></tr>\n"
	} else {
	    puts $wf "<td align=center><a href=\"$sgfpath\">$gid</a></td><td>$wn</td><td>$tw</td><td><b>$bn</b></td><td>$tb</td><td>$res</td></tr>\n"
	}

	set tcc [expr $tcc ^ 1]
    }

    puts $wf "</table></center>\n"
    puts $wf "</body>"

    # ---------------------------------------------------------------------------------------------------------

    puts $wf "</html>"

    close $wf
    file rename -force $tmpfile $pageName

    foreach n [array names bcr] {
	crosstable $n
    }

}



set cfg [lindex $argv 0]
if { [ catch {source $cfg} ] } {
    puts "Error reading config file"
    exit 0
}


if { [catch {sqlite3 db $database_state_file} ] } {
    puts "Error opening $cgi_database datbase."
    exit 1
}

db timeout 60000


proc  update_ratings {} {
    global rating

    db transaction {
	set nrk [db eval {SELECT name, rating, K from password}]
    }
    
    foreach {nme rat k} $nrk {
	
	set rat [expr {int($rat + 0.5)}]
	
	if { $k <= 16.0 } {
	    set rating($nme) $rat
	} else {
	    set rating($nme) "$rat?"
	}
    }
}



#  cgi eval { INSERT INTO games VALUES($gid, $w, $wsrate, $b, $bsrate, $dte, $res) }
if { [catch {sqlite3 cgi $cgi_database} ] } {
    puts "Error opening $cgi_database datbase."
    exit 1
}

set  tmpfile "$htmlDir/standings.tmp"
set pageName "$htmlDir/standings.html"


set ct 0
set count 0

while 1 {
    set x [file mtime $web_data_file]

    puts $web_data_file

    if { $x != $ct } {
	incr count
	# puts "$count) File changed!"

	update_ratings
	buildWebPage

	set ct $x
    }

    after 28000
}
