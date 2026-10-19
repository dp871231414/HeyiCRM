package com.heyi.modules.system.service.impl;

import com.heyi.modules.system.mapper.OrganizationMapper;
import com.heyi.modules.system.service.OrganizationService;
import com.heyi.publics.common.base.SuperServiceImpl;
import com.heyi.publics.entity.Organization;
import org.springframework.stereotype.Service;

@Service
public class OrganizationServiceImpl extends SuperServiceImpl<OrganizationMapper, Organization> implements OrganizationService {
}
