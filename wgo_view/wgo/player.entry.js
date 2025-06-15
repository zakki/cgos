// Aggregate player scripts to build full player bundle
import { WGo } from './wgo';

import './kifu';
import './sgfparser';
import './player';
import { BasicPlayer} from './basicplayer';
import './basicplayer.component';
import './basicplayer.infobox';
import './basicplayer.commentbox';
import './basicplayer.control';
import './player.editable';
import './player.cgos';
import './scoremode';
import './player.permalink';

WGo.BasicPlayer = BasicPlayer;
