package com.heyi.modules.system.manager;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.heyi.modules.system.mapper.RoleMapper;
import com.heyi.publics.common.base.BaseEntity;
import com.heyi.publics.entity.Role;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class RoleManager {

    private final RoleMapper roleMapper;

    public boolean existsName(String name, Long excludeId) {
        LambdaQueryWrapper<Role> q = new LambdaQueryWrapper<Role>()
                .eq(Role::getName, name)
                .apply("deleted_at = 0");
        if (excludeId != null) {
            q.ne(BaseEntity::getId, excludeId);
        }
        return roleMapper.selectCount(q) > 0;
    }
}
