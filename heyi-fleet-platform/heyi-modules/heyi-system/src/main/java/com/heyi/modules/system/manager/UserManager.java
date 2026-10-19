package com.heyi.modules.system.manager;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.heyi.modules.system.mapper.UserMapper;
import com.heyi.publics.common.base.BaseEntity;
import com.heyi.publics.entity.User;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class UserManager {

    private final UserMapper userMapper;

    public User selectByAccount(String account) {
        LambdaQueryWrapper<User> q = new LambdaQueryWrapper<User>()
                .eq(User::getAccount, account)
                .apply("deleted_at = 0");
        return userMapper.selectOne(q);
    }

    public boolean existsAccount(String account, Long excludeId) {
        LambdaQueryWrapper<User> q = new LambdaQueryWrapper<User>()
                .eq(User::getAccount, account)
                .apply("deleted_at = 0");
        if (excludeId != null) {
            q.ne(BaseEntity::getId, excludeId);
        }
        return userMapper.selectCount(q) > 0;
    }

    public long countByRole(Long roleId) {
        LambdaQueryWrapper<User> q = new LambdaQueryWrapper<User>()
                .eq(User::getRoleId, roleId)
                .apply("deleted_at = 0");
        return userMapper.selectCount(q);
    }

    /** 部门下账号数（部门删除约束） */
    public long countByDept(Long deptId) {
        LambdaQueryWrapper<User> q = new LambdaQueryWrapper<User>()
                .eq(User::getDeptId, deptId)
                .apply("deleted_at = 0");
        return userMapper.selectCount(q);
    }
}
