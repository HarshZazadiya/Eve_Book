def two_sum(nums):
    num_dict = {}
    for i, num in enumerate(nums):
        if num in num_dict:
            return [num_dict[num], i]
        num_dict[num] = i
    return []