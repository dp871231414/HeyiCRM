package com.heyi.modules.system.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.heyi.publics.entity.Organization;
import org.apache.ibatis.annotations.Param;

import java.util.List;

public interface OrganizationMapper extends BaseMapper<Organization> {

    /** 按父节点取子节点（已过滤逻辑删除），定义于 OrganizationMapper.xml */
    List<Organization> selectByParentId(@Param("parentId") Long parentId);
}
