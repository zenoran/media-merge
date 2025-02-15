"# media-merge" 

This script will cleanup movie and tv libraries.

*Merge*
 - renames directory names to a common format
 - merges multiple directories with the same title together

*Cleanup*
 - cleans up empty folders
 - cleans up extra garbage files like .nfo, etc.
 - takes into consideration filesize (over 1gb) to still nuke samples


Operation can be done in interactive mode which will prompt for every action
or in a forced mode for scheduling to run via cron or something.