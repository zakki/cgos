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
package provide app-gogo 1.0

package require Tk
package require gogame


array set gamelist {}

set hcp(9)   [list 2 4 6]
set hcp(11)  [list 3 5 7]
set hcp(13)  [list 3 6 9]
set hcp(15)  [list 3 7 11]
set hcp(17)  [list 3 8 13]
set hcp(19)  [list 3 9 15]


# set up image directory
# ----------------------
set  idir "$starkit::topdir/lib/app-gogo/images"

set  server localhost
set  port   1415



class game_board {

    variable  gme
    variable  n
    variable  gid

    common  bgcolor \#c1a274

    common  ssz  22   ;# based on graphics images
    common  half 11
    common  boff 33
    common  csz  
    common  bdimg  [image create photo -file "$idir/wood.gif"]
    common  wstone [image create photo -file "$idir/wstone.gif"]
    common  bstone [image create photo -file "$idir/bstone.gif"]
    common  bd_bg_color  \#ffffff
    common  fleg [list A B C D E F G H J K L M N O P Q R S T U V W X Y Z]
    common  rleg [list 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25]

    # note: only works for boardsize 9
    common hcp     [list 2 4 6]

    constructor {gameid size blackName whiteName} {

      set gid  $gameid
      set n    $size	
      set csz  [expr {($n + 2) * $ssz}]

      gogame gme $n

      toplevel .$gid -width [expr ($n + 8) * $ssz] -height [expr ($n + 7) * $ssz] -bg $bgcolor

      canvas .$gid.bd  -bg $bd_bg_color -height $csz  -width $csz -bd 3 -relief groove

      label .$gid.bwho  -bg \#404040 -fg \#ffffff -text "Black: $blackName"  -anchor w
      place  .$gid.bwho  -x [expr $half + 4] -y 12 -width $csz

      label .$gid.wwho  -bg \#f0f0f0 -fg \#000000 -text "White: $whiteName"  -anchor w
      place  .$gid.wwho  -x [expr $half + 4]  -y [expr  4 + $ssz + $half] -width $csz

      for {set a 0} {$a < 21} {incr a} {
	  for {set b 0} {$b < 21} {incr b} {
	      .$gid.bd create image [expr $a * 96] [expr $b * 96] -anchor nw -image $bdimg 
	  }
      }

      # Draw the board on the canvas
      # ----------------------------
      for {set i 0} { $i < $n } { incr i } {
	  set  os [expr $boff + $ssz * $i]
	  set  ex [expr $half + $n * $ssz]
	  .$gid.bd create line $os  $boff  $os $ex
	  .$gid.bd create line $boff $os $ex $os
	  
	  # draw the file legend
	  # --------------------
	  set ch [lindex $fleg $i]
	  .$gid.bd create text $os [expr $ssz * 0.75]  -text $ch
	  .$gid.bd create text $os [expr $ssz * $n + ($ssz * 1.3)]  -text $ch
	  
	  # draw the rank legend
	  # --------------------
	  set ch [lindex $rleg [expr $n - $i - 1]]
	  .$gid.bd create text [expr $ssz * 0.95] [expr 1 + $os] -text $ch -anchor e
	  .$gid.bd create text [expr $ssz * $n + ($ssz * 1.1)] [expr 1 + $os] -text $ch -anchor w
      }

      # set handicapp points
      # --------------------
      if {$n >= 9 && $n <= 19} {
	  if {[expr $n & 1] == 1} {
	      foreach xx $hcp {
		  foreach yy $hcp {
		      .$gid.bd create oval [expr -2 + $boff + $ssz * $xx] [expr -2 + $boff + $ssz * $yy] [expr 2 + $boff + $ssz * $xx] [expr 2 + $boff + $ssz * $yy]
		      .$gid.bd create oval [expr -1 + $boff + $ssz * $xx] [expr -1 + $boff + $ssz * $yy] [expr 1 + $boff + $ssz * $xx] [expr 1 + $boff + $ssz * $yy]
		  }
	      }
	  }
      }

      # make the game score buttons
      # ---------------------------
      set  sv 0
      set y [expr $boff + $ssz * ($n + 4)]

      for {set ix 0} {$ix < 6} {incr ix} {
	  set x [expr 4 + $half + $ix * 40]
	  button .$gid.mvb$ix -text [lindex $a $ix] -relief flat -background $bgcolor
	  place .$gid.mvb$ix -x $x -y $y -width 38
      }

      place  .$gid.bd  -x $half  -y [expr $ssz * 3]
  }


    # display the board
    # -----------------
    method  updateBoard {} {
	
	set  nn [expr $n * $n]
	set stones [gme getboard]
	
	.$gid.bd delete stone
	
	for {set j 0} {$j < $nn} { incr j } {
	    
	    set c [lindex $stones $j]
	    if {$c == 1} {
		
		set yy [expr $j / $n]
		set xx [expr $j % $n]
		
		.$gid.bd create image [expr $boff + $ssz * $xx] [expr $boff + $ssz * $yy] -image $wstone -tags stone
	    }
	    
	    if {$c == 2} {
		
		set yy [expr $j / $n]
		set xx [expr $j % $n]
		
		.$gid.bd create image [expr $boff + $ssz * $xx] [expr $boff + $ssz * $yy] -image $bstone -tags stone
	    }
	}
    }


    method updateGameScore {} {
	set a [gme list_moves]
	set count [llength $a]

	if { $count <= 6 } { 
	    set sv 0
	} else { 
	    set sv [expr $count - 6]
	}

	set bn 0
	while {$sv < $count} {
	    .$gid.mvb$bn configure -text [lindex $a $sv]
	    incr sv
	    incr bn
	}
    }


    method makeMove {mv} {
	gme make $mv 
	updateBoard
	updateGameScore
    }


}



# game_board gb99 99 9 "GnuGo-3.7.4(1830)" "Lazarus-1.14(1945)"

# set x "gb99"
# $x makeMove e5
# $x makeMove d4
# $x makeMove g6
# $x makeMove f5
# $x makeMove pass

wm geometry . "600x400"
# wm resizable . 0 0

# set up several labels in the window

proc BindYview { lists args } {
    foreach l $lists {
	eval {$l yview} $args
    }
}

frame .gdis -relief flat 
listbox .gdis.glistG -relief flat -borderwidth 1 -width 10 -yscrollcommand { .gdis.scroll set}
listbox .gdis.glistW -relief flat -borderwidth 1 -width 24 -yscrollcommand { .gdis.scroll set}
listbox .gdis.glistB -relief flat -borderwidth 1 -width 24 -yscrollcommand { .gdis.scroll set}
listbox .gdis.glistR -relief flat -borderwidth 1 -width 10 -yscrollcommand { .gdis.scroll set}
scrollbar .gdis.scroll -command [list BindYview [list .gdis.glistG .gdis.glistB .gdis.glistW .gdis.glistR]]
pack .gdis.scroll -side right -fill y
pack .gdis.glistG -side left 
pack .gdis.glistB -side left 
pack .gdis.glistW -side left 
pack .gdis.glistR -side left 

pack .gdis 

# foreach {z} [list 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21] {
#    .gdis.glistG insert end "$z"
#    .gdis.glistB insert end "is"
#    .gdis.glistW insert end "the"
#    .gdis.glistR insert end "deal"
# }




proc get_message {sock} {

    global gamelist

    if {[catch {read -nonewline $sock} data] || [eof $sock]} {
	catch {close $sock}
    } else {
	set d [split $data "\n"]
	foreach data $d {

	    puts $data
	    set msg [split $data]
	    set key [lindex $msg 0]
	    
	    if {$key == "match"} {
		
		# match 11 AnchorMan(1500) wimpy(1500) 1155239441
		
		set gid [lindex $msg 1]
		set bid [lindex $msg 2]
		set wid [lindex $msg 3]
		set stt [lindex $msg 4]
		set brt -
		set wrt -
		set res -
		
		set gamelist($gid) [list $gid $bid $wid $stt $brt $wrt $res]
		# puts $gamelist($gid)
		.gdis.glistG insert 0 $gid
		.gdis.glistB insert 0 $bid
		.gdis.glistW insert 0 $wid 
		.gdis.glistR insert 0 -
	    }
	    
	    if {$key == "gameover"} {
		
		# gameover 11 AnchorMan(1500) 85.072 wimpy(1499) 95.676 B+17.5
		
		set gid [lindex $msg 1]
		set bid [lindex $msg 2]
		set brt [lindex $msg 3]
		set wid [lindex $msg 4]
		set wrt [lindex $msg 5]
		set res [lindex $msg 6]
		set stt [lindex $gamelist($gid) 2]
		set gamelist($gid) [list $gid $bid $wid $stt $brt $wrt $res]
		# puts $gamelist($gid)
		.gdis.glistG insert 0 $gid
		.gdis.glistB insert 0 $bid
		.gdis.glistW insert 0 $wid 
		.gdis.glistR insert 0 $res
	    }
	}
    }
}



set err [catch {set sock [socket $server $port]} msg]
if {$err} {
    puts stderr "could not execute"
    exit 1
}

fconfigure $sock -buffering line -blocking 0

# Set up handler to "respond" when a message comes in
# ---------------------------------------------------
fileevent $sock readable [list get_message $sock]



