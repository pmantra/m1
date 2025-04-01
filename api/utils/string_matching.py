def hamming_distance(str1: str, str2: str) -> int:
    # Find the length of the longer string
    max_len = max(len(str1), len(str2))

    # Pad the shorter string with spaces to make them equal in length
    str1 = str1.ljust(max_len)
    str2 = str2.ljust(max_len)

    # Initialize the distance counter
    distance = 0

    # Iterate over the characters in the strings and count differences
    for char1, char2 in zip(str1, str2):
        if char1 != char2:
            distance += 1

    return distance
