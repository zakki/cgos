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
package provide app-cgos 3.0

package require gogame
package require sqlite3

set SKIP 4


# READ the configuration file
# ---------------------------
if { $argc < 1 } {
    puts "Must specify a configuration file."
    exit 1
} else {
    set cfg [lindex $argv 0]
    if { [ catch {source $cfg} ] } {
	puts "Error reading config file"
	exit 0
    }

    set level [expr $level * 1000]

    set leeway [expr int($timeGift * 1000.0)]

    set tme [clock format [clock seconds] -format "%Y-%m-%d %H:%M:%S" -timezone :UTC]
    puts "\"$serverName\" up and running at $tme GMT"
}

# remove any existing kill file
# -----------------------------
file delete -force $killFile


set workdir [file dirname $web_data_file]


# make GameDir directory if it doesn't exist
# -------------------------------------------
if { [catch {file mkdir $sgfDir} ] } {
    puts "error making sgfDir: $gameDir"
    exit 1
}


if {![file exists $cgi_database]} {
    sqlite3 cgi $cgi_database

    cgi eval {
	create table games(gid int, w, wr,  b, br,  dte, res);
	create index white on games(w);
	create index black on games(b);
    }
    cgi close
}



if {![file exists $game_archive_database]} {
    sqlite3 dbrec $game_archive_database

    dbrec eval {
	create table games(gid int, dta)
    }

    dbrec close
}



if {![file exists $database_state_file]} {

    sqlite3 db $database_state_file

    db eval {
	create table gameid(gid int);
	create table password(name, pass, games int, rating, K, last_game, primary key(name) );
	create table games(gid int, w, wr, b, br, dte, wtu, btu, res, final, primary key(gid));
	create table anchors(name, rating, primary key(name));
	create table clients( name, count );
	INSERT into gameid VALUES(1);
    }

    db close 
} 


if { [catch {sqlite3 db $database_state_file} ] } {
    puts "Error opening $database_state_file datbase."
    exit 1
}


if { [catch {sqlite3 cgi $cgi_database} ] } {
    puts "Error opening $cgi_database datbase."
    exit 1
}


if { [catch {sqlite3 dbrec $game_archive_database}] } {
    puts "Error opeing $game_archive_database database."
    exit 1
}


# set up a long timeout for transactions
# --------------------------------------
db     timeout 40000  
cgi    timeout 80000
dbrec  timeout 40000



# -------------------------------------------------------------------------
#  act - internal currently active users. 
#        A record exists if a user is logged on.
#        this is an array variable:  act(name) = [ list socket  msg_sent ]
# -------------------------------------------------------------------------
#  key is user_name
#  ---------------------
#  0:  socket 
#  1:  msg_state
#  2:  gid          (or zero if none is being played)
#  3:  rating
#  4:  k


# -----------------------------------------------
# games - currently active games and their states
#
# -----------------------------------------------
#  key is gid
#
#  0: white  user name
#  1: black  user name
#  2: last move start time
#  3: wrt
#  4: brt
#  5: wrate
#  6: brate
#  7: list of moves/time pairs


# -------------------------------------------------
# vact - record of an active viewers
# key is a VID (viewer ID),  val is a socket number
# -------------------------------------------------
# obs - a hash indexed by gid - who is viewing?
# obs( gid ) - a list of viewers of this game






array set act {}       ;# users currently logged on
array set games {}     ;# currently active games
array set id {}        ;# map sockets to user names
array set ratingOf {}  ;# ratings of any player who logs on
array set obs {}       ;# index by vid
array set vact {}      ;# key=vid, val=socket


# a unique and temporary name for each login until a name is established
# ----------------------------------------------------------------------
set sid 0


proc  send {sock msg} {
    if { [catch { puts $sock $msg }] } {
        set who "<unknown>"
        catch { set who $id($sock) }
        log "alert: Socket crash for user: $who"
    }
}


# send a message to a player without knowing the socket
# -----------------------------------------------------
proc  nsend {name  msg} {
    global  act
    if { [info exists act($name)] } {
	set sok [lindex $act($name) 0]
	send $sok $msg
    } else {
        log "alert: Cannot find active record for $name"
    }
}



# -------------------------------------------------
# send an informational message out to all clients
# -------------------------------------------------
proc infoMsg {msg} {
    global  act
    global  vact

    foreach {k v} [array get act] {
	if {[lindex $v 1] != "protocol"} {
	    set soc [lindex $v 0]
	    puts $soc "info $msg"
	}
    }

    # send message to viewing clients also
    # -------------------------------------
    foreach {k v} [array get vact] {
	if {[lindex $v 1] != "protocol"} {
	    catch {puts $v "info $msg"}
	}
    }

}






proc log {msg} {
    set tme [clock format [clock seconds] -format "%Y-%m-%d %H:%M:%S" -timezone :UTC]
    puts  "$tme | $msg" 
}


# routines to rate the games 
# --------------------------

proc  expectation  {me you} {
    set x [expr {($you - $me) / 400.0}]
    set  d [expr {1.0 + pow(10.0, $x)}]
    expr 1.0 / $d
}



proc  newrating { cur_rating  opp_rating  res  K } {
    set ex [expectation $cur_rating $opp_rating]
    set nr [expr {$cur_rating + $K * ($res - $ex)}]
    return $nr
}


# returns an SGF game record
# ---------------------------
proc sgf {gid res dte err} {

    global boardsize
    global komi
    global level
    global serverName
    global games

    set   ctm 0
    array set colstr {0 B 1 W}

    lassign $games($gid) w b dmy wrt brt wrate brate mvs

    set lv [expr {$level / 1000}]

    set s "(;GM\[1\]FF\[4\]CA\[UTF-8\]\n"
    append s "RU\[Chinese\]SZ\[$boardsize\]KM\[$komi\]TM\[$lv\]\n"

    set comment $err

    append s "PW\[$w\]PB\[$b\]WR\[$wrate\]BR\[$brate\]DT\[$dte\]PC\[$serverName\]RE\[$res\]GN\[$gid\]\n"

    set tmc 0  ;# total move count

    foreach {m t} $mvs {

	set mv [string tolower $m]
	set tleft [expr {$t / 1000}]

	if {[regexp {^pas} $mv]} {
	    append s ";$colstr($ctm)\[\]$colstr($ctm)L\[$tleft\]"
	    incr tmc
	    if {$tmc > 7} {
		append s "\n"
		set tmc 0
	    }
	} else {
	    set ccs [scan [string index $mv  0] %c]
	    set rrs [string range $mv 1 end]
	    if {$ccs > 104} {
		incr ccs -1
	    }
	    set ccs [binary format c $ccs]
	    set rrs [expr ($boardsize - $rrs) + 97]
	    set rrs [binary format c $rrs]
	    append s ";$colstr($ctm)\[$ccs$rrs\]$colstr($ctm)L\[$tleft\]"
	    incr tmc
	    if {$tmc > 7} {
		append s "\n"
		set tmc 0
	    }
	}
	set ctm [expr {$ctm ^ 1}]
    }

    if { $comment != "" } {
	append s ";C\[$comment\]\n"
    }

    append s ")\n"

    return $s
}



# write an SGF game record
# ---------------------------
proc seeRecord {gid res dte tme} {

    global boardsize
    global komi
    global level
    global games

    lassign $games($gid) w b dmy wrt brt wrate brate mvs

    set  s {}

    append s "$tme $boardsize $komi $w\($wrate\) $b\($brate\) $level [join $mvs] "
    append s $res

    return $s
}




proc  batchRate {} {

    global minK
    global maxK
    global act
    global ratingOf

    array set anchors {}

    set tme [clock format [clock seconds] -format "%Y-%m-%d %H:%M:%S" -timezone :UTC]

    foreach {nme rat} [db eval {SELECT name, rating FROM anchors}] {
	set anchors($nme) $rat
    }


    set batch [db eval {SELECT gid, w, b, res, dte  FROM games WHERE final == "n"}]
    
    set kRange [expr {$maxK - $minK}]

    foreach {gid w b res dte} $batch {
	lassign [db eval {SELECT rating, K FROM password WHERE name = $w}] wr wk
	lassign [db eval {SELECT rating, K FROM password WHERE name = $b}] br bk

	if { $wk < $minK } { set wk $minK }
	if { $bk < $minK } { set bk $minK }

	# calculate white and black K strength (percentage of total K range)
	# used to calculate effective K for individual games and K reduction
	# ------------------------------------------------------------------
	set wks [expr {1.0 - ($wk-$minK) / $kRange} ]
	set bks [expr {1.0 - ($bk-$minK) / $kRange} ]

	set weK [expr $wk * $bks]   ;# white effective K for this game
	set beK [expr $bk * $wks]   ;# black effective K for this game

	if { [string index $res 0] == "W" } { set wres 1.0 } else { set wres 0.0 }
	set bres [expr 1.0 - $wres]

	set nwr [newrating $wr $br $wres $weK]
	set nbr [newrating $br $wr $bres $beK]

	# reduce K based on strength of opponents K factor
	# but reduce it less if it's already below 32
	# ------------------------------------------------
	if { $wk <= 32.0 } { set rf 0.02 } else { set rf 0.04 }
	set nwK [expr {$wk * (1.0 - $rf * $bks)}]

	if { $bk <= 32.0 } { set rf 0.02 } else { set rf 0.04 }
	set nbK [expr {$bk * (1.0 - $rf * $wks)}]


	# limit K to minimum value
	# ------------------------
	if { $nbK < $minK } { set nbK $minK }
	if { $nwK < $minK } { set nwK $minK }

	# make sure anchors retain their ratings
	# --------------------------------------
	if { [info exists anchors($w)] } { set nwr $anchors($w) ; set nwK $minK }
	if { [info exists anchors($b)] } { set nbr $anchors($b) ; set nbK $minK }

	# update act record too
	# ---------------------
	if {[info exists act($w)]} {lset act($w) 3 $nwr ; lset act($w) 4 $nwK}
	if {[info exists act($b)]} {lset act($b) 3 $nbr ; lset act($b) 4 $nbK}
	set ratingOf($w) [strRate $nwr $nwK]
	set ratingOf($b) [strRate $nbr $nbK]

	set wsrate [strRate $nwr $nwK]
	set bsrate [strRate $nbr $nbK]
	
	db transaction immediate {
	    db eval { UPDATE password SET rating=$nwr, K=$nwK, last_game=$tme, games=games+1 WHERE name==$w }
	    db eval { UPDATE password SET rating=$nbr, K=$nbK, last_game=$tme, games=games+1 WHERE name==$b }
	    db eval { UPDATE games SET final="y" WHERE gid=$gid }
	}
	cgi eval { INSERT INTO games VALUES($gid, $w, $wsrate, $b, $bsrate, $dte, $res) }

    }
}




proc test_password {pass} {

    if { [string is ascii $pass] } {
	set e {[^\d\w\.-]}
	
	if { [regexp {[^\d\w\.-]} $pass] } {
	    set msg "Password must only alphanumeric, underscore, hyphen, period or digits characters."
	    return $msg
	}
    } else {
	set msg "Password must consist of only ascii characters."
	return $msg
    }

    if {[string length $pass] < 3} {
	set msg "Password must be at least 3 characters."
	return $msg
    }

    if {[string length $pass] > 16} {
	set msg "Password limited to 16 characters."
	return $msg
    }

    return ""

}


proc valid_name {user_name} {

    if { [string is ascii $user_name] } {
	set e {[^\d\w\.-]}
	
	if { [regexp {[^\d\w\.-]} $user_name] } {
	    set msg "User name must only alphanumeric, underscore, hyphen, period or digits characters."
	    return $msg
	}
    } else {
	set msg "User name must consist of only ascii characters."
	return $msg
    }

    if {[string length $user_name] < 3} {
	set msg "User name must be 3 characters or more."
	return $msg
    }

    if {[string length $user_name] > 18} {
	set msg "User name must be no more than 18 characters long."
	return $msg
    }

    return ""

}


# produce a printable rating given rating and K
# ---------------------------------------------
proc strRate {elo k} {

    set r [format "%0.0f" $elo]

    if { $r < 0.0 } { set r 0 }
    if { $k > 16.0 } { set r "$r?" }

    return $r
}



# produce a printable rating from active record
# ---------------------------------------------
proc rating {who} {
    global  act

    lassign $act($who) dmy0 dmy1 dmy2 rat k
    
    return [strRate $rat $k]
}








proc  gameover {gid sc err} {
    global  games
    global  level
    global  act
    global  vact
    global  sgfDir
    global  htmlDir
    global  obs
    global  id

    delete object gme$gid      ;# free memory of the game object

    lassign $games($gid) w b lmst wrt brt wr br lst    
    log "gameover: $gid $w $b $sc $err"

    set ctime [clock seconds]

    set dte [clock format $ctime -format "%Y-%m-%d" -timezone :UTC]
    set tme [clock format $ctime -format "%Y-%m-%d %H:%M" -timezone :UTC]

    if { [info exists act($w)] } {
	nsend $w "gameover $dte $sc $err"
	lset act($w) 1 "gameover"
    }

    if { [info exists act($b)] } {
	nsend $b "gameover $dte $sc $err"
	lset act($b) 1 "gameover"
    }

    set wtu [expr {$level - $wrt}]
    set btu [expr {$level - $brt}]

    # send gameover announcements to viewing clients
    # ----------------------------------------------
    foreach {k v} [array get vact] {
	catch {send $v "gameover $gid $sc $wtu $btu"}
    }

    if {[info exists obs($gid)]} {
	foreach v $obs($gid) {
	    catch {send $vact($v) "update $gid $sc"}
	}
	unset obs($gid)
    }


    set sgfString [sgf $gid $sc $dte $err]
    set see [seeRecord $gid $sc $dte $tme]

    set  dest_dir "$htmlDir/$sgfDir/[clock format $ctime -format "%Y/%m/%d" -timezone :UTC]"
    file mkdir $dest_dir   ;# make directory if it doesn't exist

    dbrec eval { INSERT INTO games VALUES($gid, $see) }
    db eval { INSERT INTO games VALUES( $gid, $w, $wr, $b, $br, $tme, $wtu, $btu, $sc, "n" ) }
    set f [open "$dest_dir/$gid.sgf" w]
    puts $f $sgfString
    close $f


    # we can kill the active game record now.
    # ----------------------------------------
    unset games($gid)  
}



proc  viewer_respond {sock} {

    global  vact
    global  id
    global  games
    global  boardsize
    global  komi
    global  obs
    global  level

    set  who $id($sock)

    # If we can no longer read from sock, close it.
    # ---------------------------------------------
    if {[catch {read -nonewline $sock} data] || [eof $sock]} {
	catch {close $sock}

	log "\[$who\] disconnected"

	unset vact($who)  
	unset id($sock)
	return
    }

    if { $data == "quit" } {
	catch {close $sock}
	log "viewer $who quits"
	unset vact($who)
	unset  id($sock)
	return
    }

    set req [lindex $data 0]

    switch $req {

	"observe" {
	    lassign $data dmy gid
	    
	    if {[info exists games($gid)]} {

		lassign $games($gid) w b lmst wrt brt wrate brate mvs
		    
		append w "($wrate)"
		append b "($brate)"
		
		log "sending to viewer: game $gid - - $boardsize $komi $w $b $level ..."

		set msg "setup $gid - - $boardsize $komi $w $b $level [join $mvs]" 
		send $sock $msg

		if {[info exists obs($gid)]} {
		    if { [lsearch -exact $who] == -1 } {
			lappend obs($gid) $who
		    }
		} else {
		    set obs($gid) [list $who]
		}

		
	    } else {
		set rec [dbrec eval {SELECT dta FROM games WHERE gid = $gid} ]
		if { $rec != "" } {
		    send $sock "setup $gid [join $rec]"
		}  else {
		    send $sock "setup $gid ?"
		}
	    }
	}
    }
}



proc  player_respond {sock} {
    global  act
    global  id
    global  games
    global  level
    global  boardsize
    global  komi
    global  defaultRating
    global  maxK
    global  ratingOf
    global  leeway
    global  sid
    global  vact
    global  obs


    set who $id($sock)

    lassign $act($who) dmy msg gid rat k

    # If we can no longer read from sock, close it.
    # ---------------------------------------------
    if {[catch {read -nonewline $sock} data] || [eof $sock]} {
	catch {close $sock}

	log "\[$who\] disconnected"

	unset act($who)  
	unset id($sock)
	return
    }

    if { $data == "quit" } {
	catch {close $sock}
	log "user $who quits"
	unset act($who)
	unset  id($sock)
	return
    }


    switch $msg {

	"protocol" {
	    set msg [string trim $data]

	    if { [string range $msg 0 1] == "v1" } {
		unset act($who)   
		set  vact($who) $sock

		# close down current handler, open a new handler
		# ----------------------------------------------
		fileevent $sock readable ""
		fileevent $sock readable [list viewer_respond $sock]

		db transaction immediate {
		    log "client: $data"
		    set cc [db eval {select count from clients where name = $data}]
		    if { [string is integer -strict $cc] } {
			db eval {update clients set count=count+1 where name = $data}
		    } else {
			db eval { insert into clients values($data, 1) }
		    }
		}


		log "\[$who\] logged on as viewer"


		# send out information about a few previous games
		# -----------------------------------------------
		foreach {gid stuff} [dbrec eval { select gid, dta from games where gid > (select max(gid) from games) - 40 order by gid }] {
		    set lst [lassign $stuff dte tme bs kom w b lev]
		    set res [lindex $lst end]
		    send $sock "match $gid $dte $tme $bs $kom $w $b $res"
		}

		# send out information about current games
		# ----------------------------------------
		foreach {gid rec} [array get games] {
		    lassign $rec w b lmst wrt brt wrate brate 
		    append w "($wrate)"
		    append b "($brate)"
		    log "sending to viewer: match $gid - - $boardsize $komi $w $b"
		    send $sock "match $gid - - $boardsize $komi $w $b -"
		}



		return
	    }


	    
	    if { [string range $msg 0 1] == "e1" } {
		db transaction immediate {
		    log "client: $data"
		    set cc [db eval {select count from clients where name = $data}]
		    if { [string is integer -strict $cc] } {
			db eval {update clients set count=count+1 where name = $data}
		    } else {
			db eval { insert into clients values($data, 1) }
		    }
		}
		lset act($who) 1 "username"
		send $sock "username"
		return
	    }

	    send $sock "Error: invalid response"
	    unset act($who)
	    unset id($sock)
	    catch {close $sock}
	    return
        }


	"username"  {

	    set data [string trim $data]
	    set err [valid_name $data]  ;# returns "" or an error message

	    if { $err == "" } {
		set user_name $data
	    } else {
		send $sock "Error: $err"
		unset act($who)
		unset  id($sock)
		catch {close $sock}

		return
	    }

            # -------------------------------------------------------------------------------------------------------
            # I think this fixes the connection bug.  When a user logs on, but the system believes he is already
            # logged on,  test to see if there is a connection by sending an informational message to old connection.
            # If this fails, then we can properly shut down the old connection and allow the new login.
            # 
            # I hesitate to simply close the old connection no matter what since the password has not yet been 
            # entered and so getting this right would require a bit more bookeeping.
            # -------------------------------------------------------------------------------------------------------
	    if { [info exists act($user_name) ] } {
                # test old connection
                set xsoc [lindex $act($user_name) 0]
                set err [catch {puts $xsoc "info another login is being attempted using this user name"}]
                if { $err } {
                    catch {close $xsock}
                    log "Error: user $user_name apparently lost old connection"
                    unset act($user_name)
                    unset  id($xsock)
                } else {
                    send  $sock "Error: You are already logged on!  Closing connection."
                    unset act($who)
                    unset id($sock)
                    catch {close $sock}
                    return
                }
	    }

	    set   id($sock) $user_name
	    unset act($who)
	    set act($user_name) [list $sock "password" 0 0 0]
	    send $sock "password"
	}


	"password" {

	    set pw [lindex [string trim $data] 0] 
	    set loginTime [clock seconds]

	    set err [test_password $pw]
	    
	    if { $err > "" } {
		send $sock "Error: $err"
		catch {close $sock}
		unset act($who)
		unset id($sock)
		return
	    }

	    lassign [db eval {SELECT pass, rating, K FROM password WHERE name = $who}] cmp_pw rat k

	    if { $cmp_pw == "" } {
		log "\[$who\] new user"
		db eval { INSERT INTO password VALUES($who, $pw, 0, $defaultRating, $maxK, "2000-01-01 00:00") }
		set cmp_pw $pw
		set rat $defaultRating
		set k $maxK
		set ratingOf($who) [strRate $rat $k]
	    } else {
		set ratingOf($who) [strRate $rat $k]
	    }

	    
	    if { $cmp_pw != $pw } {
		send $sock "Sorry, password doesn't match"
		catch {close $sock}
		unset act($who)
		unset id($sock)
		return
	    } 

	    log "\[$who] logged on"

	    lset act($who) 3 $rat
	    lset act($who) 4 $k
	    lset act($who) 1 "waiting"

	    log "is $who currently playing a game?"

	    # determine if there are any games pending
	    # ----------------------------------------
	    foreach {gid inf}  [array get games]  {
		lassign $inf w b 

		log "testing $gid $w $b"

		# is this player involved in a game?
		# ----------------------------------
		if { $w == $who || $b == $who } {
		    log "YES!"
		    lassign $inf w b lmst wrt brt wrat brat mvs
		    set wr $ratingOf($w)
		    set br $ratingOf($b)

		    set msg_out "setup $gid $boardsize $komi $level $w\($wr\) $b\($br\) [join $mvs]"
		    log $msg_out

		    # determine who's turn to play
		    # ----------------------------
		    set ply [llength $mvs]
		    set ply [expr {$ply / 2}]
		    if { $ply & 1 } { set ctm $w } else { set ctm $b }

		    # catch up the game
		    # ------------------
		    send $sock $msg_out

		    lset act($who) 1 "ok"
		    lset act($who) 2 $gid 

		    # determine if we need to send out a genmove command
		    # --------------------------------------------------
		    if { $ctm == $who } {
			if { $ply & 1 } { 
			    set tr $wrt 
			    set ct [clock milliseconds]
			    set tl [expr {$wrt - ($ct - $lmst)}]
			    send $sock "genmove w $tl"
			    lset act($who) 1 "genmove"
			    return
			} else {
			    set tr $brt 
			    set ct [clock milliseconds]
			    set tl [expr {$brt - ($ct - $lmst)}]
			    send $sock "genmove b $tl"
			    lset act($who) 1 "genmove"
			    return
			}
		    }
		}
	    }

	}

	"gameover" {

	    set msg [string trim $data]
	    # log "msg recieved from $who is $msg"

	    if { $msg == "ready" } {
		lset act($who) 1 "waiting"
		lset act($who) 2 0
		return
	    } else {
		lset act($who) 1 "gameover"
	    }

	    
	    
	    log "\[$who\] gave improper response to gameover: $msg"
	    # nsend $who "Error: improper response to gameover"
	    
	    # unset act($who)
	    # catch { close $sock }
	}


	"genmove" {

	    set ct [clock milliseconds]
	    lset act($who) 1 "ok"                       ;# passive state - not expecting a response


	    # does game still exist?
	    # ----------------------
	    set gid [lindex $act($who) 2]              

	    # put program in wait state if it has already completed
	    # -----------------------------------------------------
	    if { ![info exists games($gid)] } {	
		lset act($who) 1 "waiting"
		return 
	    }


	    set ctm [gme$gid colorToMove]               ;# who's turn to move?
	    set maybe [lindex "W+ B+" [expr $ctm & 1]]  ;# opponent wins if there is an error


	    set mv [string trim $data]
	    set over ""

	    lassign $games($gid) w b lmst wrt brt wrate brate mvs

	    # make time calc, determine if game over for any reason
	    # -----------------------------------------------------

	    set tt [expr $ct - $lmst - $leeway]             ;# fudge an extra moment

	    if { $tt < 0 } { set tt 0 }

	    if { $ctm & 1 } {
		set wrt [expr {$wrt - $tt}]
		lset games($gid) 3 $wrt
		if { $wrt < 0 } {
		    set over "B+Time"
		    gameover $gid $over ""
		    return
		}
	    } else {
		set brt [expr {$brt - $tt}]
		lset games($gid) 4 $brt
		if { $brt < 0 } {
		    set over "W+Time"
		    gameover $gid $over ""
		    return
		}
	    }


	    if { [string tolower $mv] == "resign" } {
		set err 0
		set over $maybe
		append over "Resign"
		if { $w == $who } { 
		    #  nsend $b "play w $mv $wrt" 
		    set vmsg "$mv $wrt"
		} else { 
		    # nsend $w "play b $mv $brt" 
		    set vmsg "$mv $brt"
		}
		if {[info exists obs($gid)]} {
		    foreach {s} $obs($gid) {
			catch { send $vact($s) "update $gid $vmsg" }
		    }
		}
		gameover $gid $over ""
		return
	    } else {
		set err [gme$gid make $mv]
	    }


	    set err_msg ""
	    if {$err < 0} {
		set xerr [expr $err * -1]
		# Return: -4  if str_move formatted wrong
		# Return: -3  move to occupied square
		# Return: -2  Position Super Ko move
		# Return: -1  suicide
		set err_msg  [list huh {suicide attempted} {KO attempted} {move to occupied point} {do not understand syntax}]
		set over $maybe
		append over "Illegal" 
		gameover $gid $over [lindex $err_msg $xerr]
		return
	    }


	    # record the moves and times
	    # --------------------------
	    if {$ctm & 1} { append mvs " $data $wrt" } else { append mvs " $data $brt" }
	    lset games($gid) 7 $mvs

	    if { $w == $who } { 
		nsend $b "play w $mv $wrt" 
		set vmsg "$mv $wrt"
	    } else { 
		nsend $w "play b $mv $brt" 
		set vmsg "$mv $brt"
	    }	    

	    if {[info exists obs($gid)]} {
		foreach {s} $obs($gid) {
		    catch { send $vact($s) "update $gid $vmsg" }
		}
	    }

	    # game over due to natural causes?
	    # --------------------------------
	    if { [gme$gid twopass] } {
		set sc [gme$gid ttScore]
		set sc [expr $sc - $komi]
		if { $sc < 0.0 } {
		    set sc [expr -$sc]
		    set over "W+$sc"
		    gameover $gid $over ""
		    return
		} else {
		    set over "B+$sc"
		    gameover $gid $over ""
		    return
		}
	    }

	    # game still in progress, start clock and send genmove
	    # -----------------------------------------------------
	    if { $w == $who } { 
		if { [info exists act($b)] } {
		    lset act($b) 1 "genmove"
		    nsend $b "genmove b $brt"		
		}
		lset games($gid) 2 [clock milliseconds]
	    } else { 
		if { [info exists act($w)] } {
		    lset act($w) 1 "genmove"
		    nsend $w "genmove w $wrt"		
		}
		lset games($gid) 2 [clock milliseconds]
	    }

	}


	"ok" {
	    log "\[$who\] made illegal respose in ok mode"
	}


    }

}



proc accept_connection {sock ip port} {
    global act
    global sid
    global defaultRating
    global id
    global maxK


    fconfigure $sock -blocking 0 -buffering line

    # create a default id till we get user name
    # -----------------------------------------
    set who $sid
    incr sid

    set id($sock) $who

    set act($who) [list $sock "protocol" 0 $defaultRating $maxK]


    # Set up handler to "respond" when a message comes in
    # ---------------------------------------------------
    fileevent $sock readable [list player_respond $sock]

    send $sock "protocol"
}


proc rcmp {a b} {
    set a1 [lindex $a 1]
    set b1 [lindex $b 1]

    if {$a1 < $b1} {
	return 1
    } elseif {$a1 > $b1} {
	return -1
    } else {
	return 0
    }
}



# --------------------------------------------------------
#  Estimate how much time left in current round in seconds
#
#  We will do it the "hard" way because of the forgiveness
#  factor given to each move can create inaccuracies.  The
#  easy way is to to take  round_start_time - (level * 2)
# ---------------------------------------------------------
proc estimateRoundTimeLeft {} {
    global  games
    global  level

    set wctl 0                           ;# worst case time left
    set mtme [clock milliseconds]    

    foreach {k v} [array get games] {
	lassign $v ww bb lmst wrt brt wrate brate
	
	set tr [expr {$wrt + $brt - ($mtme - $lmst)}]
	if {$tr > $wctl} { set wctl $tr }
    }
    
    return [expr $wctl / 1000]
}





#  -----------------------------------------------------------
#  schedule_game
# 
#  1. Determine if any games are complete due to time forfeit
#  2. complete and record those games
#  3. If NO games are left, schedule a new round
#  4. set up event loop for next cycle
#  -----------------------------------------------------------

set last_game_count -1

proc  schedule_games {} {

    global  SKIP
    global  act
    global  vact
    global  boardsize
    global  komi
    global  games
    global  level
    global  last_game_count
    global  web_data_file
    global  workdir
    global  killFile
    global  last_round_time
    global  leeway
    global  last_est

    set  RANGE 500.0  ;# minmum elo range allowed

    # determine if all games are complete
    # -----------------------------------
    set ct [clock milliseconds]

    set count 0   ;# number of active games

    foreach {gid rec} [array get games] {

	lassign $rec w b lmst wrt brt wrate brate mvs

	set ctm [gme$gid colorToMove]
	
	if {$ctm & 1} {
	    set tr $wrt 
	    set tu [expr $ct - $lmst - $leeway]
	    if {$tu < 0} { set tu 0 }
	    set time_left [expr $tr - $tu]
	    if { $time_left < 0 } {
		lset games($gid) 3 $time_left
		gameover $gid "B+Time" ""
		incr  count  ;# so that we get to recyle
	    } else {
		incr count
	    }
	} else {
	    set tr $brt 
	    set tu [expr $ct - $lmst - $leeway]
	    if {$tu < 0} { set tu 0 }
	    set time_left [expr $tr - $tu]
	    if { $time_left < 0 } {
		lset games($gid) 4 $time_left
		gameover $gid "W+Time" ""
		incr count    ;# so that we get to recyle
	    } else  {
		incr count
	    }
	}	    
    }

    if { $count != $last_game_count } {
	log "Games in progress: $count"
	set last_game_count $count
    }


    # send progress message
    # ---------------------
    if { 1 } {

	set  est [estimateRoundTimeLeft]
	set estMin [expr $est / 60]
	set estSec [expr $est % 60]
	
	set curTime [clock seconds]
	if { $curTime - $last_est > 60 } {
	    if { $est > 2 } {
		infoMsg [format "Maximum time until next round: %02d:%02d" $estMin $estSec]
	    }
	    set last_est $curTime
	}
    }


    # should we begin another round of scheduling?
    # --------------------------------------------
    if { $count == 0 } {

	log "Batch rating"
	batchRate

	set tmpf "$workdir/dta.cgos.tmp"
	set wd [open $tmpf w]
	set ctme  [clock seconds]
	puts $wd [clock format $ctme -format "%Y-%m-%d %H:%M:%S" -timezone :UTC]

	# prepare lookup of all players who have played within last 6 months
	# ------------------------------------------------------------------
	set atme  [expr $ctme - 86400 * 190]  
	set lutme [clock format $atme -format "%Y-%m-%d %H:%M:%S" -timezone :UTC]
	foreach {nme gms rat k lg} [db eval {SELECT name, games, rating, K, last_game FROM password WHERE last_game >= $lutme}] {
	    puts $wd "u $nme $gms [strRate $rat $k] $lg"
	}

	# recently completed games
	# ------------------------
	set atme [expr $ctme - 3600 * 4]  ;# get 4 hours worth of games
	set lutme [clock format $atme -format "%Y-%m-%d %H:%M:%S" -timezone :UTC]
	foreach {gid w wr b br dte wtu btu res} [db eval {SELECT gid, w, wr, b, br, dte, wtu, btu, res FROM games WHERE dte >= $lutme}] {
	    puts $wd "g $gid $w $wr $b $br $dte $wtu $btu $res"
	}

	
	if { [file exists $killFile] } {
	    close $wd
	    file rename -force $tmpf $web_data_file
	    db close 
	    log "KILL FILE FOUND - EXIT CGOS"
	    exit 0
	}


	# dynamically computer ELO RANGE
	# ------------------------------
	set lst {}

	foreach {name v} [array get act] {
	    lassign $v sock state gid rating

	    if { $state == "waiting" } {
		set r $rating
		lappend lst [list $name $r]
	    }
	}

	set lst [lsort -command rcmp $lst]
	set max_interval 0
	
	set ll [llength $lst]
	set e [expr $ll - $SKIP]

	for {set i 0} {$i < $e} {incr i} {
	    set  cr [lindex [lindex $lst $i] 1]
	    set  nr [lindex [lindex $lst [expr $i + $SKIP]] 1]
	    
	    set  diff [expr {$cr - $nr}]

	    if {$diff > $max_interval} {
		set max_interval $diff
	    }
	}

	# cover the case where there are very few players
	# -----------------------------------------------
	if { $e <= 0 } {
	    set max_interval 2000.0
	}

	log "maximum skip elo: $max_interval"
	set max_interval [expr $max_interval * 1.50]

	if { $max_interval > $RANGE } {
	    set RANGE $max_interval
	}

	log "ELO permutation factor to be used: $RANGE"


	# now permute the players up to RANGE amount
	# ------------------------------------------
	set lst {}

	foreach {name v} [array get act] {
	    lassign $v sock state gid rating

	    if { $state == "waiting" } {
		set r [expr $rating + $RANGE * rand()]
		lappend lst [list $name $r]
	    }
	}

	set lst [lsort -command rcmp $lst]

	if { [llength $lst] > 1 } {

	    log "will schedule: [llength $lst] players"

	    foreach {aa bb} $lst {
		
		if { $bb != "" } {
		    
		    # set up white and black players
		    # ------------------------------
		    set wp [lindex $aa 0]  ;# actual player names
		    set bp [lindex $bb 0]  ;# actual player names
		    
		    set wco [db eval {SELECT count(*) FROM games WHERE w==$wp AND b==$bp}]
		    set bco [db eval {SELECT count(*) FROM games WHERE w==$bp AND b==$wp}]
		    
		    # swap white and black if black has not been played as many times
		    if { $bco < $wco } { set tmp $bp ; set bp $wp ; set wp $tmp }
		    
		    set gid [db eval {SELECT gid FROM gameid WHERE ROWID=1}]
		    db eval {UPDATE gameid set gid=gid+1 WHERE ROWID=1}
		    gogame gme$gid $boardsize

		    set wr [lindex $act($wp) 3]
		    set wk [lindex $act($wp) 4]
		    set br [lindex $act($bp) 3]
		    set bk [lindex $act($bp) 4]
		    set wr [strRate $wr $wk]
		    set br [strRate $br $bk]

		    set games($gid) [list $wp $bp 0 $level $level $wr $br {}]
		    lset act($wp) 2 $gid
		    lset act($bp) 2 $gid
		    set msg_out "setup $gid $boardsize $komi $level $wp\($wr\) $bp\($br\)"
		    nsend $wp $msg_out
		    nsend $bp $msg_out

		    set vmsg "match $gid - - $boardsize $komi $wp\($wr) $bp\($br\) -"
		    foreach {vk vv} [array get vact] {
			send $vv $vmsg
		    }

		    log "starting $wp $wr $bp $br"
		}
	    }

	    
	    # add a 5 second delay to let all programs complete setup.
	    # ------------------------------------------------------

	    after 3000

	    set view_count [llength [array names vact]]
	    log "Active viewers: $view_count"

	    
	    # gentlemen, start your clocks!
	    # -------------------------------------
	    set tmeSch [clock format [clock seconds] -format "%Y-%m-%d %H:%M:%S" -timezone :UTC]
	    foreach {gid rec} [array get games] {
		lassign $rec wp bp 
		log "match-> $wp\([rating $wp]\)   $bp\([rating $bp]\)"
		nsend $bp "genmove b $level"          ;# the game's afoot
		set ct [clock milliseconds]
		lset games($gid) 2 $ct
		lset act($bp) 1 "genmove"
		lset act($wp) 1 "ok"
		puts $wd [join "s $tmeSch $gid $rec"]
	    }
	}

	close $wd
	file rename -force $tmpf $web_data_file
    }

    after idle [list after 15000 schedule_games]    ;# every 15 seconds
}


set last_est [clock seconds]


# Create our server on the expected port
# ------------------------------------------
socket -server accept_connection $portNumber


# Create a game scheduling event
# ------------------------------

# after 50000 schedule_games    
after 45000 schedule_games    



# Drop Tcl into the event loop
vwait forever

