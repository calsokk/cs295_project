local M = {}

function M.create(name: string, value: number)
    return {name = name, value = value}
end

function M.process(item: {name: string, value: number}): string
    return `{item.name}: {item.value}`
end

local item = M.create("test", 42)
print(M.process(item))

return M
