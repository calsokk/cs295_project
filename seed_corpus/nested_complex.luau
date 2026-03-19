local function fibonacci(n: number): number
    if n <= 1 then
        return n
    end
    return fibonacci(n - 1) + fibonacci(n - 2)
end

local function quicksort(arr: {number}, lo: number, hi: number)
    if lo < hi then
        local pivot = arr[hi]
        local i = lo - 1
        for j = lo, hi - 1 do
            if arr[j] <= pivot then
                i = i + 1
                arr[i], arr[j] = arr[j], arr[i]
            end
        end
        arr[i + 1], arr[hi] = arr[hi], arr[i + 1]
        local p = i + 1
        quicksort(arr, lo, p - 1)
        quicksort(arr, p + 1, hi)
    end
end

type TreeNode<T> = {
    value: T,
    left: TreeNode<T>?,
    right: TreeNode<T>?,
}

local function depth<T>(node: TreeNode<T>?): number
    if node == nil then
        return 0
    end
    local l = depth(node.left)
    local r = depth(node.right)
    return 1 + if l > r then l else r
end

print(fibonacci(10))

local data = {5, 3, 8, 1, 9, 2, 7}
quicksort(data, 1, #data)
for _, v in ipairs(data) do
    print(v)
end
