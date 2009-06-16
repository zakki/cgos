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
package require botnoid


set  bsz 9

set hcp(9)   [list 2 4 6]
set hcp(11)  [list 3 5 7]
set hcp(13)  [list 3 6 9]
set hcp(15)  [list 3 7 11]
set hcp(17)  [list 3 8 13]
set hcp(19)  [list 3 9 15]


# set up image directory
# ----------------------
set  idir "$starkit::topdir/lib/app-gogo/images"

botnoid::newgame $bsz 5 0   ;# newgame with no handicap

set engine_mv ""


set  ssz  22                        ;# square size
set  half [expr $ssz / 2]           ;# half a sqaure
set  boff [expr $ssz * 1.5]         ;# half a sqaure
set  csz  [expr ($bsz + 2) * $ssz]  ;# size of the canvas

set  fleg [list A B C D E F G H J K L M N O P Q R S T U V W X Y Z]
set  rleg [list 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25]

# set  bd_bg_color   \#CFC7AF  ;# board background color

set  bd_bg_color  \#ffffff

set bdimg [image create photo -file "$idir/wood.gif"]
# set bkimg [image create photo -file "$idir/hwood.gif"]
set bkimg [image create photo -file "$idir/brd5.ppm"]


set wstone [image create photo -file "$idir/wstone.gif"]
set bstone [image create photo -file "$idir/bstone.gif"]


# set wstone [image create photo -file "$idir/whitestone.ppm"]
# set bstone [image create photo -file "$idir/blackstone.ppm"]


wm geometry . "[expr ($bsz + 9) * $ssz]x[expr ($bsz + 4) * $ssz]"
wm resizable . 0 0


canvas .bground -height [expr ($bsz + 4) * $ssz] -width [expr ($bsz + 9) * $ssz]
canvas .bd  -bg $bd_bg_color -height $csz  -width $csz -bd 3 -relief groove -cursor hand2
# frame  .gscore  -height [expr $bsz * $ssz]  -width [expr $ssz * 5] -relief groove -bd 3 -background ""


for {set a 0} {$a < 10} {incr a} {
    for {set b 0} {$b < 10} {incr b} {
	.bground create image [expr $a * 96] [expr $b * 96] -anchor nw -image $bkimg 
    }
}

.bground create text [expr ($bsz + 4.1) * $ssz] [expr $ssz * 1.5] -text "BLACK" -anchor w -font bold
.bground create text [expr ($bsz + 6.6) * $ssz] [expr $ssz * 1.5] -text "WHITE" -anchor w -font bold



# make a big board
# ---------------------------------
if {5==5} {
 for {set a 0} {$a < 21} {incr a} {
    for {set b 0} {$b < 21} {incr b} {
	.bd create image [expr $a * 96] [expr $b * 96] -anchor nw -image $bdimg 
     }
 }
} else {
    .bd create image 0 0 -anchor nw -image $bkimg 
}



set xx [expr ($bsz + 4.0) * $ssz]
set yy [expr $ssz * 2.0]
set cy [expr $yy + (($bsz + .20) * $ssz)]

.bground create rectangle $xx $cy [expr $xx + 96] [expr $cy + 20] -tags "passtg passbox" -fill \#e0e0c0
.bground create text [expr $xx + 25]  [expr $cy + 4] -text PASS -tags "passtg passb" -anchor nw

.bground bind "passtg" <ButtonPress-1> {
    .bground itemconfigure passbox -fill \#ffffff
}


proc  execute_mv {mv} {
    gme make $mv
    botnoid::play_move $mv
    updateBoard
    update_game_score
}



proc moveCycle {} {
    
    global thinking

    set  pot_mv [botnoid::think_cycle]

    if { $pot_mv != "" } {
	execute_mv $pot_mv
	set thinking 0
    } else {
	after idle [list moveCycle]
    }
}





.bground bind "passtg" <ButtonRelease-1> {
    .bground itemconfigure passbox -fill \#e0e0c0

    set ctm [gme colorToMove]
    set err [gme make pass]

    botnoid::play_move pass
    
    if {[gme twopass]} {
	set dead [botnoid::dead_stones]
	set fbd [gme getFinalBoard $dead]
	markBoard $fbd
    } else {
	set thinking 1
	botnoid::init_thinking 0  ;# set up for searching
	moveCycle
	break
    }
    
    update_game_score 
    
}




proc update_game_score {} {
    
    global bsz
    global ssz


    .bground delete mvlab

    set a [gme list_moves]
    set count [llength $a]

    set st [expr $count - ($bsz * 2)]
    
    if { $st < 0 } { set st 0 }
    if { [expr $st & 1] != 0 } { incr st }

    set  col 0
    set  lin 0
    set  xx [expr ($bsz + 4.0) * $ssz]
    set  yy [expr $ssz * 2.0]

    for {set ix $st} {$ix < $count} {incr ix} {
	
	set txt [lindex $a $ix]

	set cx [expr $xx + (($col * 2.4) * $ssz)]
	set cy [expr $yy + ($lin * $ssz)]
	.bground create rectangle $cx $cy [expr $cx + 44] [expr $cy + 20] -tags [list mvlab mv$ix rec$ix] -fill \#e0e0c0 
	.bground create text [expr $cx + 4]  [expr $cy + 4] -text $txt -tags [list mvlab mv$ix] -anchor nw


	.bground bind "mv$ix" <ButtonPress-1> {
	    set tlist [.bground find closest %x %y]
	    set tlist [.bground gettags [lindex $tlist 0]]
	    set tgix [lsearch -regexp $tlist {^mv\d}]
	    if {$tgix >= 0} {
		set tg [lindex $tlist $tgix]
		set tg [regsub -all mv $tg rec]
		.bground itemconfigure $tg -fill \#ffffff
	    }
	}
	
	.bground bind "mv$ix" <ButtonRelease-1> {
	    set tlist [.bground find closest %x %y]
	    set tlist [.bground gettags [lindex $tlist 0]]
	    set tgix [lsearch -regexp $tlist {^mv\d+}]
	    if {$tgix >= 0} {
		set tg [lindex $tlist $tgix]
		set tg [regsub -all mv $tg rec]
		.bground itemconfigure $tg -fill \#e0e0c0
	    }
	}


	incr col

	if {$col > 1} {
	    set col 0
	    incr lin
	}
    }
}




# Draw the appropriate lines 
# --------------------------
for {set i 0} { $i < $bsz } { incr i } {

    .bd create line [expr $boff + $ssz * $i]  $boff  [expr $boff + $ssz * $i]  [expr $half + $bsz * $ssz] 
    .bd create line $boff [expr $boff + $ssz * $i]  [expr $half + $bsz * $ssz] [expr $boff + $ssz * $i]  

    # draw the file legend
    # --------------------
    set ch [lindex $fleg $i]
    .bd create text [expr $boff + $ssz * $i] [expr $ssz * 0.75]  -text $ch
    .bd create text [expr $boff + $ssz * $i] [expr $ssz * $bsz + ($ssz * 1.3)]  -text $ch

    # draw the rank legend
    # --------------------
    set ch [lindex $rleg [expr $bsz - $i - 1]]
    .bd create text [expr $ssz * 0.95] [expr 1 + $boff + $ssz * $i] -text $ch -anchor e
    .bd create text [expr $ssz * $bsz + ($ssz * 1.1)] [expr 1 + $boff + $ssz * $i] -text $ch -anchor w
}



# set handicapp points
# --------------------
if {$bsz >= 9 && $bsz <= 19} {

    if {[expr $bsz & 1] == 1} {

	foreach xx $hcp($bsz) {
	    foreach yy $hcp($bsz) {
		.bd create oval [expr -2 + $boff + $ssz * $xx] [expr -2 + $boff + $ssz * $yy] [expr 2 + $boff + $ssz * $xx] [expr 2 + $boff + $ssz * $yy] 
	    }
	}
    }
}





proc XyNotate {x y} {
    global bsz
    return [format "%s%d" [string range "ABCDEFGHJKLMNOPQRSTUVWXYZ" $x $x] [expr $bsz - $y]]
}


set stillx -9
set stilly -9

set curx -9
set cury -9
set curmv ""
set thinking 0
set block 0

gogame gme $bsz


set computers_color 1    ;# computers color



bind .bd <Motion> {

    if {$thinking} { break }

    # Determine which intersection the mouse is on if any
    # ---------------------------------------------------
    set y [expr  int( 0.5 + ((%y - $boff) / $ssz))]
    set x [expr  int( 0.5 + ((%x - $boff) / $ssz))]
    
    if {$x != $curx || $y != $cury} {
	.bd configure -cursor hand2
    }
    
    
    if {$x != %x || $y != %y} {
	
	set ctm [expr [gme colorToMove] & 1]
	
	.bd delete transit
	
	if {$ctm & 1} {
	    .bd create image %x %y -image $wstone -tags transit
	} else {
	    .bd create image %x %y -image $bstone -tags transit
	}
	
    } 
}



bind .bd <Leave> {
    .bd delete transit
}


bind .bd <ButtonRelease-1> {

}


bind .bd  <ButtonPress-3> {

    if {$thinking} { break }

    set ctm [gme colorToMove]

    if {[gme unmake]} {
	botnoid::undo
	set computers_color [expr $computers_color ^ 1]
    }

    updateBoard
    update_game_score
}




bind .bd  <ButtonPress-1> {

    if {$thinking} { break }

    set ctm [gme colorToMove]

    .bd delete transit
    .bd delete marker


    # Determine which intersection mouse is on if any
    # -----------------------------------------------
    set y [expr  int( 0.5 + ((%y - $boff) / $ssz))]
    set x [expr  int( 0.5 + ((%x - $boff) / $ssz))]

    if {$x >= 0 && $x < $bsz && $y >= 0 && $y < $bsz} {

	set mv [XyNotate $x $y]
	
	set err [gme make $mv]

	if {$err >= 0} {
	    updateBoard
	    update_game_score
	    set curx $x
	    set cury $y
	    set curmv $mv
	    botnoid::play_move $mv 

	    set thinking 1
	    botnoid::init_thinking 0  ;# set up for searching
	    moveCycle

	    # set engine_mv [gen_move 0]
	    # execute_mv $engine_mv

	} else {
	    set curx -9
	    set cury -9
	    set ltxt "Unknown Error"
	    if {$err == -3} {set ltxt "Occupied"}
	    if {$err == -2} {set ltxt "Illegal KO"}
	    if {$err == -1} {set ltxt "Suicide"}
	    .bd create rectangle [expr %x - 40] [expr %y - 26] [expr %x + 40] [expr %y -10] -fill white -tags curlab
	    .bd create text %x [expr %y - 17] -text "$ltxt" -tags curlab
	    after 1000 {.bd delete curlab }
	    set thinking 0
	    set block 0
	}
    }
}





# display the board
# -----------------
proc  updateBoard {} {

    global bsz
    global boff
    global ssz
    global bstone
    global wstone

    set  nn [expr $bsz * $bsz]
    set stones [gme getboard]
    
    .bd delete stone
    
    for {set j 0} {$j < $nn} { incr j } {
	
	set c [lindex $stones $j]
	if {$c == 1} {
	    
	    set yy [expr $j / $bsz]
	    set xx [expr $j % $bsz]
	    
	    .bd create image [expr $boff + $ssz * $xx] [expr $boff + $ssz * $yy] -image $wstone -tags stone
	}
	
	if {$c == 2} {
	    
	    set yy [expr $j / $bsz]
	    set xx [expr $j % $bsz]
	    
	    .bd create image [expr $boff + $ssz * $xx] [expr $boff + $ssz * $yy] -image $bstone -tags stone
	}
    }
}



# mark the board according to the final status
# --------------------------------------------

proc  markBoard {marks} {

    global bsz
    global boff
    global ssz
    global bstone
    global wstone

    set  nn [expr $bsz * $bsz]
    set stones $marks

    
    for {set j 0} {$j < $nn} { incr j } {
	
	set c [lindex $stones $j]
	if {$c == 1} {
	    
	    set yy [expr $j / $bsz]
	    set xx [expr $j % $bsz]

	    .bd create rectangle [expr -4 + $boff + $ssz * $xx] [expr -4 + $boff + $ssz * $yy] [expr 4 + $boff + $ssz * $xx] [expr 4 + $boff + $ssz * $yy] -tags marker -fill \#e0e0e0 -outline \#101010
	}
	
	if {$c == 2} {
	    
	    set yy [expr $j / $bsz]
	    set xx [expr $j % $bsz]

	    .bd create rectangle [expr -4 + $boff + $ssz * $xx] [expr -4 + $boff + $ssz * $yy] [expr 4 + $boff + $ssz * $xx] [expr 4 + $boff + $ssz * $yy] -tags marker -fill \#101010 -outline \#e0e0e0
	}
    }
}




place  .bground -x 0 -y 0
place  .bd  -x 10  -y $ssz
# place  .gscore -x [expr ($bsz + 3.4) * $ssz]  -y [expr $ssz * 1.5]
