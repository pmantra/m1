def find_number_of_segments(data: dict) -> int:
    cnt = 0

    for _, value in data.items():
        if isinstance(value, list):
            for item in value:
                cnt += find_number_of_segments(item)
        else:
            cnt += 1
    return cnt
