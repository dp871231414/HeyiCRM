package com.heyi.modules.system.manager;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.heyi.modules.system.mapper.OrganizationMapper;
import com.heyi.publics.common.base.BaseEntity;
import com.heyi.publics.entity.Organization;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
@RequiredArgsConstructor
public class OrganizationManager {

    private final OrganizationMapper organizationMapper;

    public List<Organization> selectByParentId(Long parentId) {
        return organizationMapper.selectByParentId(parentId);
    }

    /** 同级重名校验（用于新增/改名） */
    public boolean existsSameLevelName(String name, Long parentId, Long excludeId) {
        LambdaQueryWrapper<Organization> q = new LambdaQueryWrapper<Organization>()
                .eq(Organization::getName, name)
                .eq(Organization::getParentId, parentId)
                .apply("deleted_at = 0");
        if (excludeId != null) {
            q.ne(BaseEntity::getId, excludeId);
        }
        return organizationMapper.selectCount(q) > 0;
    }

    /** 部门下是否存在账号（删除约束） */
    public boolean hasChildren(Long parentId) {
        LambdaQueryWrapper<Organization> q = new LambdaQueryWrapper<Organization>()
                .eq(Organization::getParentId, parentId)
                .apply("deleted_at = 0");
        return organizationMapper.selectCount(q) > 0;
    }
}
