package com.heyi.publics.common.aspect;

import cn.dev33.satoken.stp.StpUtil;
import com.heyi.publics.common.annotation.DynamicUserFields;
import com.heyi.publics.common.base.BaseEntity;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.springframework.stereotype.Component;

/**
 * 自动填充 createdBy / updatedBy：取当前登录账号，未登录时留空。
 */
@Aspect
@Component
public class UserFieldFillAspect {

    @Around("@annotation(dynamicUserFields)")
    public Object fill(ProceedingJoinPoint joinPoint, DynamicUserFields dynamicUserFields) throws Throwable {
        String loginAccount = currentAccount();
        if (loginAccount != null) {
            for (Object arg : joinPoint.getArgs()) {
                fillEntity(arg, loginAccount);
            }
        }
        return joinPoint.proceed();
    }

    private void fillEntity(Object arg, String account) {
        if (!(arg instanceof BaseEntity entity)) {
            return;
        }
        if (entity.getCreatedBy() == null || entity.getCreatedBy().isEmpty()) {
            entity.setCreatedBy(account);
        }
        entity.setUpdatedBy(account);
    }

    private String currentAccount() {
        try {
            if (!StpUtil.isLogin()) {
                return null;
            }
            Object loginId = StpUtil.getLoginId();
            return loginId == null ? null : String.valueOf(loginId);
        } catch (Exception e) {
            return null;
        }
    }
}
