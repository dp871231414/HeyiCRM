package com.heyi.modules.system.service.impl;

import com.heyi.modules.system.mapper.RoleMapper;
import com.heyi.modules.system.service.RoleService;
import com.heyi.publics.common.base.SuperServiceImpl;
import com.heyi.publics.entity.Role;
import org.springframework.stereotype.Service;

@Service
public class RoleServiceImpl extends SuperServiceImpl<RoleMapper, Role> implements RoleService {
}
