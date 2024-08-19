# dv_merge

Experimental tool for merging raw DV video files.  This is a simple tool with some key input requirements:

- The files must be of the same length (same exact file size).
- Corresponding frames must have the same frame number / byte offset in every input file.

Based on these requirements, the tool can be more resilient to DV timecode errors that might challenge an alternative algorithm that tries to match corresponding frames using DV timecodes.  Instead, it simply assumes that corresponding frames are at the same position.  The output file is guaranteed to have the exact same frame count as all the input files.

The tool has two merge algorithms that can be specified with the `--merge-algorithm` argument:

- `analysis`: Runs both DV Analyzer and DVRescue analysis tools against the inputs.  The output frame is chosen from an input that has no analysis errors from either tool, if possible.  If only one tool reported an issue, preference is given to clean DVRescue results.
- `binary`: A very simplistic n-way binary merge of the inputs.  The most common byte at each byte position is selected in the output.  This will result in the output raw frame data being a blend of the inputs.  Note that since I don't have a copy of the DV specifications, it's unclear how safe this really is.  It's possible it could result in something that other decoders might struggle with.
