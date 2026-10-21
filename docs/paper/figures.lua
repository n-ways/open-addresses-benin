-- In the PDF a figure uses its vector PDF; the markdown on the web uses the SVG.
function Image(img)
  img.src = img.src:gsub('%.svg$', '.pdf')
  return img
end

-- File paths in inline code may break after a slash or a dot, so they never run into the margin.
function Code(c)
  if FORMAT ~= 'latex' or not c.text:find('[/.]') or c.text:find(' ') then
    return nil
  end
  local t = c.text:gsub('[\\{}_#%%&%$~^]', function(ch)
    local map = {['\\'] = '\\textbackslash{}', ['{'] = '\\{', ['}'] = '\\}', ['_'] = '\\_', ['#'] = '\\#',
                 ['%'] = '\\%', ['&'] = '\\&', ['$'] = '\\$', ['~'] = '\\textasciitilde{}', ['^'] = '\\textasciicircum{}'}
    return map[ch]
  end)
  t = t:gsub('([/.])', '%1\\allowbreak{}')
  return pandoc.RawInline('latex', '\\texttt{' .. t .. '}')
end
