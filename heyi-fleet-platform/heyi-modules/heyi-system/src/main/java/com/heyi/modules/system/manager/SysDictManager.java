package com.heyi.modules.system.manager;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.heyi.modules.system.mapper.SysDictItemMapper;
import com.heyi.modules.system.mapper.SysDictMapper;
import com.heyi.publics.common.base.BaseEntity;
import com.heyi.publics.entity.SysDict;
import com.heyi.publics.entity.SysDictItem;
import com.heyi.publics.util.JsonUtil;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

@Component
@RequiredArgsConstructor
public class SysDictManager {

    private final SysDictMapper sysDictMapper;
    private final SysDictItemMapper sysDictItemMapper;

    public List<String> selectValues(Long dictId) {
        LambdaQueryWrapper<SysDictItem> q = new LambdaQueryWrapper<SysDictItem>()
                .eq(SysDictItem::getDictId, dictId)
                .apply("deleted_at = 0")
                .orderByAsc(SysDictItem::getSort);
        List<SysDictItem> items = sysDictItemMapper.selectList(q);
        List<String> values = new ArrayList<>();
        for (SysDictItem item : items) {
            values.add(item.getValue());
        }
        return values;
    }

    /** 枚举值整份替换：先逻辑删除旧值，再写入新值 */
    public void replaceValues(Long dictId, List<String> values) {
        LambdaQueryWrapper<SysDictItem> q = new LambdaQueryWrapper<SysDictItem>()
                .eq(SysDictItem::getDictId, dictId)
                .apply("deleted_at = 0");
        List<SysDictItem> olds = sysDictItemMapper.selectList(q);
        for (SysDictItem old : olds) {
            old.setDeletedAt(System.currentTimeMillis());
            sysDictItemMapper.updateById(old);
        }
        if (values == null) {
            return;
        }
        int sort = 0;
        for (String v : values) {
            if (v == null || v.trim().isEmpty()) {
                continue;
            }
            SysDictItem item = new SysDictItem();
            item.setId(com.heyi.publics.common.util.IdUtil.nextId());
            item.setDictId(dictId);
            item.setValue(v.trim());
            item.setSort(sort++);
            item.setDeletedAt(0L);
            sysDictItemMapper.insert(item);
        }
    }

    public SysDict selectByCode(String code) {
        LambdaQueryWrapper<SysDict> q = new LambdaQueryWrapper<SysDict>()
                .eq(SysDict::getCode, code)
                .apply("deleted_at = 0");
        return sysDictMapper.selectOne(q);
    }

    public String toJson(List<String> permissions) {
        return JsonUtil.write(permissions);
    }
}
