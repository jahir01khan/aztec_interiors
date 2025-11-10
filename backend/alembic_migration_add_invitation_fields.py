from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_invitation_fields'
down_revision = None  # Update this to your latest migration ID
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns for invitation system
    op.add_column('users', sa.Column('is_invited', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('invitation_token', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('invited_at', sa.DateTime(), nullable=True))
    
    # Create index on invitation_token for faster lookups
    op.create_index('ix_users_invitation_token', 'users', ['invitation_token'], unique=True)


def downgrade():
    # Remove index first
    op.drop_index('ix_users_invitation_token', table_name='users')
    
    # Remove columns
    op.drop_column('users', 'invited_at')
    op.drop_column('users', 'invitation_token')
    op.drop_column('users', 'is_invited')