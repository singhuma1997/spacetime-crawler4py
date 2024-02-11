#!/bin/bash

# Set target directory 
DIR="."

# Files to conditionally delete
FILES=("report_data.log" "invalid_url.log")

# Get input (0 to keep, 1 to delete) 
DELETE=$1

# Loop through files
for FILE in $DIR/*
do
  if [[ "$FILE" == "$DIR/frontier"* ]]; then
    rm "$FILE"
  fi

  for delete_file in "${FILES[@]}"
  do 
    if [[ "$DELETE" -eq 1 ]] && [[ "$FILE" == "$DIR/$delete_file" ]]; then
      rm "$FILE"
    fi

    if [[ "$DELETE" -eq 0 ]] && [[ "$FILE" == "$DIR/$delete_file" ]]; then
      echo "Keeping $delete_file"
    fi
  done

done